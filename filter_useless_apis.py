#!/usr/bin/env python3
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
"""Run an experiment with one function-under-test."""

import dataclasses
import logging
import os
import shutil
from multiprocessing import pool
from typing import List, Optional

from data_prep import project_targets
from data_prep.project_context.context_introspector import ContextRetriever
from experiment import builder_runner as builder_runner_lib
from experiment import evaluator as exp_evaluator
from experiment import oss_fuzz_checkout, textcov
from experiment.benchmark import Benchmark
from experiment.workdir import WorkDirs
from llm_toolkit import models, output_parser, prompt_builder, prompts

logger = logging.getLogger(__name__)

# WARN: Avoid high value for NUM_EVA for local experiments.
# NUM_EVA controls the number of fuzz targets to evaluate in parallel by each
# experiment, while {run_all_experiments.NUM_EXP, default 2} experiments will
# run in parallel.
NUM_EVA = int(os.getenv('LLM_NUM_EVA', '3'))
DEBUG: bool = True

# Default LLM hyper-parameters.
# #182 shows Gemini returns NUM_SAMPLES independent responses via repeated
#  queries, which generally performs better than top-k responses from one
#  query [1].
# [1] TODO(@happy-qop): Update the link.
# WARN: Avoid large NUM_SAMPLES in highly parallelized local experiments.
# It controls the number of LLM responses per prompt, which may exceed your
# LLM's limit on query-per-second.
NUM_SAMPLES = 1
MAX_TOKENS: int = 2000
RUN_TIMEOUT: int = 30
TEMPERATURE: float = 0

RESULTS_DIR = './results'


def analzye_api_prompt_llm(benchmark: Benchmark,
                     model: models.LLM,
                     prompt:dict,
                     work_dirs: WorkDirs,
                     builder: prompt_builder.PromptBuilder,
                     debug: bool = DEBUG) -> list[str]:
  """Generates fuzz target with LLM."""
  # logger.info('Generating targets for %s %s using %s..', benchmark.project,
              # benchmark.function_signature, model.name)
              
  logger.info('Analyzing %s %s using %s..', benchmark.project,
              benchmark.function_signature, model.name)
  
  model.query_llm(prompt, response_dir=work_dirs.raw_targets, log_output=debug)

  # _, target_ext = os.path.splitext(benchmark.target_path)
  generated_targets = []
  for file in os.listdir(work_dirs.raw_targets):
    if not output_parser.is_raw_output(file):
      continue
    raw_output = os.path.join(work_dirs.raw_targets, file)
    # target_code = output_parser.parse_code(raw_output)
    # target_code = builder.post_process_generated_code(target_code)
    # target_id, _ = os.path.splitext(raw_output)
    # target_file = f'{target_id}{target_ext}'
    # target_path = os.path.join(work_dirs.raw_targets, target_file)
    # output_parser.save_output(target_code, target_path)
    # generated_targets.append(target_path)

    if os.path.exists(raw_output):
      generated_targets.append(raw_output)

      logger.info('Generated:\n %s', raw_output)

  return generated_targets

  # if generated_targets:
  #   targets_relpath = map(os.path.relpath, generated_targets)
  #   targets_relpath_str = '\n '.join(targets_relpath)
  #   logger.info('Generated:\n %s', targets_relpath_str)
  # else:
  #   logger.info('Failed to generate targets: %s', generated_targets)
  # return generated_targets



def prepare(oss_fuzz_dir: str) -> None:
  """Prepares the experiment environment."""
  oss_fuzz_checkout.clone_oss_fuzz(oss_fuzz_dir)
  oss_fuzz_checkout.postprocess_oss_fuzz()


def analyze_api(model: models.LLM,
                                  benchmark: Benchmark,
                                  work_dirs: WorkDirs,
                                  template_dir: str,
                                  use_context: bool,
                                  example_pair: list[list[str]],
                                  debug: bool = DEBUG,
                                  prompt_builder_to_use: str = 'DEFAULT',
                                  # cloud_experiment_bucket: str = '',
                                  dry_run: bool = False) -> List[str]:
  """Generates a set of harnesses and build scripts ready to be evaluated
    by `check_targets`. This is where the core first LLM logic is used to
    generate harnesses.

    Returns a list of folders with the generated artifacts.
    """
  # logger.info('Generating targets')
  logger.info('Analyzing %s %s using %s..', benchmark.project,
              benchmark.function_signature, model.name)


  retriever = ContextRetriever(benchmark)
  context_info = retriever.get_context_info()

  builder = prompt_builder.FilterAPITemplateBuilder(model, benchmark,
                                                    template_dir)

  prompt_list = builder.build(project_context_content=context_info)
  prompt = {
    "messages": prompt_list,
    "temperature": TEMPERATURE,
    "max_tokens": 300,
    "top_p": 1.0,
  }
  
  os.makedirs("./results_kx", exist_ok=True)
  import json
  with open(f'./results_kx/{benchmark.project}_{benchmark.function_name}.json', 'w') as f:
    # save the prompt to a file
    json.dump(prompt, f)


  if dry_run:
    return []

  generated_targets = analzye_api_prompt_llm(benchmark,
                                       model,
                                       prompt,
                                       work_dirs,
                                       builder,
                                       debug=debug)
  # generated_targets = fix_code(work_dirs, generated_targets)
  return generated_targets


def run_filter_api(benchmark: Benchmark,
        model: models.LLM,
        template_dir: str,
        work_dirs: WorkDirs,
        example_pair: Optional[list[list[str]]] = None,
        debug: bool = DEBUG,
        cloud_experiment_name: str = '',
        cloud_experiment_bucket: str = '',
        use_context: bool = False,
        run_timeout: int = RUN_TIMEOUT,
        dry_run: bool = False,
        prompt_builder_to_use: str = 'DEFAULT'):
  """Generates code via LLM, and evaluates them."""
  
  model.cloud_setup() # Setup cloud environment if needed.

  if example_pair is None:
    example_pair = prompt_builder.EXAMPLES[benchmark.language]

  generated_targets = analyze_api(
      model=model,
      benchmark=benchmark,
      work_dirs=work_dirs,
      template_dir=template_dir,
      use_context=use_context,
      example_pair=example_pair,
      debug=debug,
      prompt_builder_to_use=prompt_builder_to_use,
      # cloud_experiment_bucket=cloud_experiment_bucket,
      dry_run=dry_run)

  logger.info('Generated %d targets', len(generated_targets))
  if not generated_targets:
    logger.error('No targets generated.')
    return None
  
  return generated_targets

  # return check_targets(model.ai_binary, benchmark, work_dirs, generated_targets,
  #                      cloud_experiment_name, cloud_experiment_bucket,
  #                      run_timeout, model.name)
