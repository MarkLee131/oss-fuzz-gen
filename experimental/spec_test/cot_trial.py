"""
Model the API by planning the logic we need to attention to.
"""
import os
import sys

sys.path.append(os.path.abspath('../../'))
import argparse
import logging
from typing import List

import openai

import run_all_experiments
from data_prep import introspector, project_targets
from data_prep.project_context.context_introspector import ContextRetriever
from experiment import benchmark as benchmarklib
from experiment.benchmark import Benchmark
from experiment.workdir import WorkDirs
from llm_toolkit import models, output_parser, prompt_builder, prompts

logger = logging.getLogger(__name__)

NUM_EVA = int(os.getenv('LLM_NUM_EVA', '3'))
DEBUG: bool = True

NUM_SAMPLES = 1
MAX_TOKENS: int = 4096
SUMMARY_MAX_TOKENS: int = 100
RUN_TIMEOUT: int = 30
TEMPERATURE: float = 0.4

RESULTS_DIR = './results_summary'
PROMPTS_DIR = './prompts'
MODEL = 'gpt-4o-azure'
os.makedirs(RESULTS_DIR, exist_ok=True)

# Set default endpoint.
introspector.set_introspector_endpoints(
    introspector.DEFAULT_INTROSPECTOR_ENDPOINT)

model = models.LLM.setup(ai_binary='',
                         name=MODEL,
                         max_tokens=MAX_TOKENS,
                         num_samples=NUM_SAMPLES,
                         temperature=TEMPERATURE)


def retrieve_all_contexts(benchmark: Benchmark,
                          cloud_experiment_bucket: str = '') -> List[str]:
  """Retrieves all contexts for the given benchmark."""

  retriever = ContextRetriever(benchmark)
  context_info = retriever.get_context_info()  # xref, source code...

  project_examples = project_targets.generate_data(
      benchmark.project,
      benchmark.language,
      cloud_experiment_bucket=cloud_experiment_bucket
  )  # existing fuzzers, the type return is a list of str list.

  # print(f'project_examples: {project_examples}')
  # convert the project examples to a list of strings
  project_examples = [f'{example}\n' for example in project_examples]

  context_info[
      'project_examples'] = project_examples  # add the project examples to the context_info, the project examples are the existing fuzzers, format is a list of dict.

  return context_info


def query_llm(prompt: str,
              response_dir: str,
              response_file_name: str = '') -> None:
  """Queries OpenAI's API and stores response in |response_dir|."""

  # construct the prompt
  prompt_dict = [{"role": "system", "content": prompt}]

  client = openai.AzureOpenAI(azure_endpoint=os.getenv(
      "AZURE_OPENAI_ENDPOINT", "https://api.openai.com"),
                              api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                              api_version=os.getenv("AZURE_OPENAI_API_VERSION",
                                                    "2024-02-01"))

  completion = client.chat.completions.create(
      messages=prompt_dict,  # type: ignore
      model=model.name,
      n=model.num_samples,
      temperature=model.temperature)

  for _, choice in enumerate(completion.choices):  # type: ignore
    content = choice.message.content
    with open(os.path.join(response_dir, f'{response_file_name}.txt'),
              'w') as f:
      f.write(content)  # type: ignore


# # prompt LLM to determine whether we need to fuzz the function by reading the function definition and the project context
# def determine_fuzz(benchmark: Benchmark, context_info: dict) -> bool:
#   """Determines whether we need to fuzz the function by reading the function
#   definition and the project context."""

#   with open(os.path.join(PROMPTS_DIR, 'summarize.txt'), 'r') as f:
#     summarize_prompt = f.read()

#   print(f'summarize_prompt: {summarize_prompt}')

#   query_llm(summarize_prompt, response_dir=RESULTS_DIR)
#   return True


def get_benchmarks(benchmarks_directory: str = '',
                   benchmark_yaml: str = '') -> list[str]:
  """
  get all benchmarks from the benchmark yaml file or directory, by revising the `prepare_experiment_targets` function within
  `run_all_experiments.py`
  
  This function will return a list of experiment configurations.
  """
  benchmark_yamls = []
  if benchmark_yaml:
    benchmark_yamls = [benchmark_yaml]

  else:
    benchmark_yamls = [
        os.path.join(benchmarks_directory, file)
        for file in os.listdir(benchmarks_directory)
        if file.endswith('.yaml') or file.endswith('yml')
    ]
  experiment_configs = []
  for benchmark_file in benchmark_yamls:
    experiment_configs.extend(benchmarklib.Benchmark.from_yaml(benchmark_file))

  return experiment_configs


def construct_prompt(benchmark: Benchmark, context_info: dict) -> str:
  """Constructs the prompt for the given benchmark and context."""

  # read the prompt template
  with open(os.path.join(PROMPTS_DIR, 'cot.txt'), 'r') as f:
    prompt_template = f.read()

  # replace the placeholders in the prompt template with the actual values

  print(
      f'type of project_examples: {type(context_info["project_examples"])}, {type(context_info["project_examples"][0])}, {len(context_info["project_examples"])}'
  )

  prompt = prompt_template.replace(
      '{API_name}', benchmark.function_name).replace(
          '{project_name}', benchmark.project).replace(
              '{function_signature}', benchmark.function_signature).replace(
                  '{source_code}', context_info['func_source']).replace(
                      '{existing_fuzz_drivers}',
                      '\n'.join(context_info['project_examples']))

  return prompt


if __name__ == '__main__':

  # experiment_targets = get_benchmarks(benchmarks_directory='', benchmark_yaml='../../benchmark-sets/comparison/ada-url.yaml')

  experiment_targets = get_benchmarks(
      benchmarks_directory='../../benchmark-sets/spec_test/', benchmark_yaml='')

  for target_benchmark in experiment_targets:

    conx = retrieve_all_contexts(benchmark=target_benchmark)
    # print(f'context_info: {conx}')
    # print to see all keys of context_info
    # print(conx.keys())

    prompt = construct_prompt(benchmark=target_benchmark, context_info=conx)
    # print(f'prompt:\n {prompt}')

    query_llm(prompt, RESULTS_DIR,
              target_benchmark.project + '_' + target_benchmark.function_name)
