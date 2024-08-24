"""
Model the API by planning the logic we need to attention to.
"""

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

NUM_EVA = int(os.getenv('LLM_NUM_EVA', '3'))
DEBUG: bool = True

NUM_SAMPLES = 1
MAX_TOKENS: int = 4096
SUMMARY_MAX_TOKENS: int = 100
RUN_TIMEOUT: int = 30
TEMPERATURE: float = 0.4

RESULTS_DIR = './results_summary'

# Use Chain of Thought to guide the specification generation


# 1. prompt LLM to determine whether we need to fuzz the function by reading the function definition and the project context
def determine_fuzz(benchmark: Benchmark, context_info: dict) -> bool:
  """Determines whether we need to fuzz the function by reading the function
  definition and the project context."""
  return False


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


def prepare(oss_fuzz_dir: str) -> None:
  """Prepares the experiment environment."""
  oss_fuzz_checkout.clone_oss_fuzz(oss_fuzz_dir)
  oss_fuzz_checkout.postprocess_oss_fuzz()


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


def run(benchmark: Benchmark,
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
  model.cloud_setup()

  if example_pair is None:
    example_pair = prompt_builder.EXAMPLES[benchmark.language]

  generated_targets = generate_targets_for_analysis(
      model=model,
      benchmark=benchmark,
      work_dirs=work_dirs,
      template_dir=template_dir,
      use_context=use_context,
      example_pair=example_pair,
      debug=debug,
      prompt_builder_to_use=prompt_builder_to_use,
      cloud_experiment_bucket=cloud_experiment_bucket,
      dry_run=dry_run)

  logger.info('Generated %d targets', len(generated_targets))
  if not generated_targets:
    return None
