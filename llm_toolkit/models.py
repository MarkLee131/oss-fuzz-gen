# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
LLM models and their functions.
"""

import logging
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import traceback
from abc import abstractmethod
from typing import Any, Callable, Optional, Type

import anthropic
import openai
import requests
import tiktoken
import vertexai
from google.api_core.exceptions import GoogleAPICallError
from vertexai import generative_models
from vertexai.preview.generative_models import GenerativeModel
from vertexai.preview.language_models import CodeGenerationModel

from llm_toolkit import prompts

logger = logging.getLogger(__name__)

# Model hyper-parameters.
MAX_TOKENS: int = 2000
NUM_SAMPLES: int = 1
TEMPERATURE: float = 0.4


class LLM:
  """Base LLM."""

  # Should be set by the subclass.
  name: str
  # TODO(mihaimaruseac): Should this be MAX_TOKENS or a different global?
  context_window: int = 2000  # Default token size.

  _max_attempts = 5  # Maximum number of attempts to get prediction response

  def __init__(
      self,
      ai_binary: str,
      max_tokens: int = MAX_TOKENS,
      num_samples: int = NUM_SAMPLES,
      temperature: float = TEMPERATURE,
      temperature_list: Optional[list[float]] = None,
  ):
    self.ai_binary = ai_binary

    # Model parameters.
    self.max_tokens = max_tokens
    self.num_samples = num_samples
    self.temperature = temperature
    self.temperature_list = temperature_list

  def cloud_setup(self):
    """Runs Cloud specific-setup."""
    # Only a subset of models need a cloud specific set up, so
    # we can pass for the remainder of the models as they don't
    # need to implement specific handling of this.

  @classmethod
  def setup(
      cls,
      ai_binary: str,
      name: str,
      max_tokens: int = MAX_TOKENS,
      num_samples: int = NUM_SAMPLES,
      temperature: float = TEMPERATURE,
      temperature_list: Optional[list[float]] = None,
  ):
    """Prepares the LLM for fuzz target generation."""
    if ai_binary:
      return AIBinaryModel(name, ai_binary, max_tokens, num_samples,
                           temperature)

    for subcls in cls.all_llm_subclasses():
      if getattr(subcls, 'name', None) == name:
        return subcls(
            ai_binary,
            max_tokens,
            num_samples,
            temperature,
            temperature_list,
        )

    raise ValueError(f'Bad model type {name}')

  @classmethod
  def all_llm_subclasses(cls):
    """All subclasses."""
    yield cls
    for subcls in cls.__subclasses__():
      yield from subcls.all_llm_subclasses()

  @classmethod
  def all_llm_names(cls):
    """Returns the current model name and all child model names."""
    names = []
    for subcls in cls.all_llm_subclasses():
      if hasattr(subcls, 'name') and subcls.name != AIBinaryModel.name:
        names.append(subcls.name)
    return names

  @abstractmethod
  def estimate_token_num(self, text) -> int:
    """Estimates the number of tokens in |text|."""

  # ============================== Generation ============================== #
  @abstractmethod
  def query_llm(self,
                prompt: prompts.Prompt | dict[str, Any],
                response_dir: str,
                log_output: bool = False) -> None:
    """Queries the LLM and stores responses in |response_dir|."""

  @abstractmethod
  def prompt_type(self) -> type[prompts.Prompt]:
    """Returns the expected prompt type."""

  def _delay_for_retry(self, attempt_count: int) -> None:
    """Sleeps for a while based on the |attempt_count|."""
    # Exponentially increase from 5 to 80 seconds + some random to jitter.
    delay = 5 * 2**attempt_count + random.randint(1, 5)
    logging.warning('Retry in %d seconds...', delay)
    time.sleep(delay)

  def _is_retryable_error(self, err: Exception, api_error: Type[Exception],
                          tb: traceback.StackSummary) -> bool:
    """Validates if |err| is worth retrying."""
    if isinstance(err, api_error):
      return True

    # A known case from vertex package, no content due to mismatch roles.
    if (isinstance(err, ValueError) and
        'Content roles do not match' in str(err) and tb[-1].filename.endswith(
            'vertexai/generative_models/_generative_models.py')):
      return True

    # A known case from vertex package, content blocked by safety filters.
    if (isinstance(err, ValueError) and
        'blocked by the safety filters' in str(err) and
        tb[-1].filename.endswith(
            'vertexai/generative_models/_generative_models.py')):
      return True

    return False

  def with_retry_on_error(self, func: Callable,
                          api_err: Type[Exception]) -> Any:
    """
    Retry when the function returns an expected error with exponential backoff.
    """
    for attempt in range(1, self._max_attempts + 1):
      try:
        return func()
      except Exception as err:
        logging.warning('LLM API Error when responding (attempt %d): %s',
                        attempt, err)
        tb = traceback.extract_tb(err.__traceback__)
        if (not self._is_retryable_error(err, api_err, tb) or
            attempt == self._max_attempts):
          logging.warning(
              'LLM API cannot fix error when responding (attempt %d) %s: %s',
              attempt, err, traceback.format_exc())
          raise err
        self._delay_for_retry(attempt_count=attempt)
    return None

  def _save_output(self, index: int, content: str, response_dir: str) -> None:
    """Saves the raw |content| from the model ouput."""
    sample_id = index + 1
    raw_output_path = os.path.join(response_dir, f'{sample_id:02}.rawoutput')
    with open(raw_output_path, 'w+') as output_file:
      output_file.write(content)


class GPT_Azure():
  """Azure's GPT model encapsulator."""

  # Should be set by the subclass.
  name: str
  # TODO(mihaimaruseac): Should this be MAX_TOKENS or a different global?
  context_window: int = 2000  # Default token size.

  _max_attempts = 5  # Maximum number of attempts to get prediction response

  def __init__(
      self,
      ai_binary: str,
      temperature_list: Optional[list[float]] = None,
  ):
    self.ai_binary = ai_binary

    if temperature_list:
      self.temperature_list = temperature_list

  name = 'azure-gpt-4o'

  # ================================ Prompt ================================ #
  def estimate_token_num(self, text) -> int:
    """Estimates the number of tokens in |text|."""
    # https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken
    try:
      encoder = tiktoken.encoding_for_model('gpt-4o')
    except KeyError:
      logger.info('Could not get a tiktoken encoding for %s.', self.name)
      encoder = tiktoken.get_encoding('cl100k_base')

    num_tokens = 0
    for message in text:
      num_tokens += 3
      for key, value in message.items():
        num_tokens += len(encoder.encode(value))
        if key == 'name':
          num_tokens += 1
    num_tokens += 3
    return num_tokens

  def prompt_type(self) -> type[prompts.Prompt]:
    """Returns the expected prompt type."""
    return prompts.OpenAIPrompt

  # ============================== Generation ============================== #
  def query_llm(self,
                prompt,
                response_dir: str,
                log_output: bool = False) -> None:
    """Queries OpenAI's API and stores response in |response_dir|."""
    if self.ai_binary:
      raise ValueError(f'OpenAI does not use local AI binary: {self.ai_binary}')

    if self.temperature_list:
      logger.info('OpenAI does not allow temperature list: %s',
                  self.temperature_list)

    API_KEY = os.getenv("AZURE_OPENAI_API_KEY", '')
    ENDPOINT = os.getenv("AZURE_OPENAI_API_ENDPOINT", '')

    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY,
    }

    # try:
    #   response = requests.post(ENDPOINT, headers=headers, json=prompt)
    #   response.raise_for_status(
    #   )  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code

    # except requests.RequestException as e:
    #   raise SystemExit(f"Failed to make the request. Error: {e}")

    logger.info(f"Sending request to Azure OpenAI API: {ENDPOINT}")

    completion = self.with_retry_on_error(
        lambda: requests.post(ENDPOINT, headers=headers, json=prompt),
        openai.OpenAIError)

    if log_output:
      logger.info(completion)
      # logger.info(completion.json())
    for index, choice in enumerate(
        completion.json()['choices']):  # type: ignore
      content = choice['message']['content']
      self._save_output(index, content, response_dir)
