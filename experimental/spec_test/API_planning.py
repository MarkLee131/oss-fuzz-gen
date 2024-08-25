"""
Model the API by planning the logic we need to attention to.
"""
import os
import sys

sys.path.append(os.path.abspath('../../'))
import logging
from typing import List

import openai
import argparse

import run_all_experiments
from data_prep import introspector, project_targets
from data_prep.project_context.context_introspector import ContextRetriever
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


def construct_prompt():
  """Constructs a prompt for the given benchmark and context."""
  ## need to mimic args, by hardcode the values, just need the `args.benchmark_yaml` or `args.benchmarks_directory`

  args = argparse.Namespace()
  args.introspector_endpoint = introspector.DEFAULT_INTROSPECTOR_ENDPOINT
  args.benchmark_yaml = '../../benchmark-sets/comparison/ada-url.yaml'
  # args.project_yaml = ''
  args.generate_benchmarks = False
  args.benchmarks_directory = ''
  # args.benchmarks_directory = '../../benchmark-sets/comparison'

  experiment_targets = run_all_experiments.prepare_experiment_targets(args)

  for target_benchmark in experiment_targets:
    retriever = ContextRetriever(target_benchmark)
    context_info = retriever._get_function_implementation()

    print(f'{context_info}')
    # break

    return context_info


def query_llm(prompt: str, response_dir: str, build_spec=False) -> None:
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

  for index, choice in enumerate(completion.choices):  # type: ignore
    content = choice.message.content
    with open(os.path.join(response_dir, f'response_{index}.json'), 'w') as f:
      f.write(content)  # type: ignore


# Use Chain of Thought to guide the specification generation


# 1. prompt LLM to determine whether we need to fuzz the function by reading the function definition and the project context
def determine_fuzz(benchmark: Benchmark, context_info: dict) -> bool:
  """Determines whether we need to fuzz the function by reading the function
  definition and the project context."""

  with open(os.path.join(PROMPTS_DIR, 'summarize.txt'), 'r') as f:
    summarize_prompt = f.read()

  print(f'summarize_prompt: {summarize_prompt}')

  query_llm(summarize_prompt, response_dir=RESULTS_DIR)
  return True


def generate_spec(benchmark: Benchmark,
                  model: models.LLM,
                  prompt: prompts.Prompt,
                  work_dirs: WorkDirs,
                  builder: prompt_builder.PromptBuilder,
                  debug: bool = DEBUG) -> list[str]:
  """Generates specification with LLM.
  Returns a filepath list of generated specifications
  """
  print(f'Generating specs for {benchmark.project} '
        f'{benchmark.function_signature} using {model.name}..')
  model.query_llm(prompt,
                  response_dir=work_dirs.raw_specification_dir,
                  build_spec=True)

  generated_specs = []
  for file in os.listdir(work_dirs.raw_specification_dir):
    if not output_parser.is_raw_output(file):
      continue
    raw_specification = os.path.join(work_dirs.raw_specification_dir, file)
    target_specification = output_parser.parse_code(raw_specification)
    target_specification = builder.post_process_generated_code(
        target_specification)
    target_id, _ = os.path.splitext(raw_specification)
    target_file = f'{target_id}.txt'
    target_path = os.path.join(work_dirs.raw_specification_dir, target_file)
    output_parser.save_output(target_specification, target_path)
    generated_specs.append(target_path)

  if generated_specs:
    targets_relpath = map(os.path.relpath, generated_specs)
    print('Generated spec:\n', '\n '.join(targets_relpath))
  else:
    print(f'Failed to generate spec: {generated_specs}')
  return generated_specs


# def prepare(oss_fuzz_dir: str) -> None:
#   """Prepares the experiment environment."""
#   oss_fuzz_checkout.clone_oss_fuzz(oss_fuzz_dir)
#   oss_fuzz_checkout.postprocess_oss_fuzz()


def generate_targets_for_analysis(model: models.LLM,
                                  benchmark: Benchmark,
                                  work_dirs: WorkDirs,
                                  template_dir: str,
                                  use_context: bool,
                                  example_pair: list[list[str]],
                                  debug: bool = DEBUG,
                                  prompt_builder_to_use: str = 'DEFAULT',
                                  cloud_experiment_bucket: str = '',
                                  dry_run: bool = False) -> List[str]:
  """Generates a set of harnesses and build scripts ready to be evaluated
    by `check_targets`. This is where the core first LLM logic is used to
    generate harnesses.

    Returns a list of folders with the generated artifacts.
    """
  logger.info('Generating targets')
  if benchmark.use_project_examples:
    project_examples = project_targets.generate_data(
        benchmark.project,
        benchmark.language,
        cloud_experiment_bucket=cloud_experiment_bucket)
  else:
    project_examples = []

  if use_context:
    retriever = ContextRetriever(benchmark)
    context_info = retriever.get_context_info()
  else:
    context_info = {}

  # If this is a test benchmark then we will use a test prompt builder.
  if benchmark.is_test_benchmark:
    logger.info('Generating a target for test case: %s',
                benchmark.test_file_path)
    builder = prompt_builder.TestToHarnessConverter(model, benchmark,
                                                    template_dir)
  elif benchmark.language == 'jvm':
    # For Java projects
    builder = prompt_builder.DefaultJvmTemplateBuilder(model, benchmark,
                                                       template_dir)
  elif prompt_builder_to_use == 'CSpecific':
    builder = prompt_builder.CSpecificBuilder(model, benchmark, template_dir)
  else:
    # Use default
    builder = prompt_builder.DefaultTemplateBuilder(model, benchmark,
                                                    template_dir)

  planning_prompt = builder.build_planning_prompt(
      benchmark,
      example_pair,
      project_example_content=project_examples,
      project_context_content=context_info)

  planning_prompt.save(work_dirs.planning_prompt)

  spec_filepath_list = generate_spec(benchmark,
                                     model,
                                     planning_prompt,
                                     work_dirs,
                                     builder,
                                     debug=debug)  # list

  prompt = builder.build_from_spec(spec_filepath_list)
  prompt.save(work_dirs.prompt)

  if dry_run:
    return []

  else:
    return spec_filepath_list


if __name__ == '__main__':
  # determine_fuzz('test', 'test')
  construct_prompt()
