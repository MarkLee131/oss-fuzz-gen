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
"""Test a fuzzer manually."""

import dataclasses
import logging
import os
import threading
from multiprocessing import pool
from typing import Any, List, Optional

from experiment import builder_runner as builder_runner_lib
from experiment import evaluator as exp_evaluator
from experiment import oss_fuzz_checkout, textcov
from experiment.benchmark import Benchmark
from experiment.workdir import WorkDirs
from llm_toolkit import models, output_parser, prompt_builder, prompts
from results import BuildResult, ExperimentResult, Result

thread_local = threading.local()

logger = logging.getLogger(__name__)

# WARN: Avoid high value for NUM_EVA for local experiments.
# NUM_EVA controls the number of fuzz targets to evaluate in parallel by each
# experiment, while {run_all_experiments.NUM_EXP, default 2} experiments will
# run in parallel.
NUM_EVA = int(os.getenv('LLM_NUM_EVA', '3'))

# Default LLM hyper-parameters.
# #182 shows Gemini returns NUM_SAMPLES independent responses via repeated
#  queries, which generally performs better than top-k responses from one
#  query [1].
# [1] TODO(@happy-qop): Update the link.
# WARN: Avoid large NUM_SAMPLES in highly parallelized local experiments.
# It controls the number of LLM responses per prompt, which may exceed your
# LLM's limit on query-per-second.
NUM_SAMPLES = 5
MAX_TOKENS: int = 4096
RUN_TIMEOUT: int = 30
TEMPERATURE: float = 0.4

RESULTS_DIR = './results'


# TODO(dongge): Move this to results.py
@dataclasses.dataclass
class AggregatedResult:
  """Aggregated evaluation result."""
  build_success_rate: float = 0.0
  crash_rate: float = 0.0
  found_bug: int = 0
  max_coverage: float = 0.0
  max_line_coverage_diff: float = 0.0
  max_coverage_sample: str = ''
  max_coverage_diff_sample: str = ''
  max_coverage_diff_report: str = ''
  full_textcov_diff: textcov.Textcov = dataclasses.field(
      default_factory=textcov.Textcov)

  def __str__(self):
    return (
        f'build success rate: {self.build_success_rate}, '
        f'crash rate: {self.crash_rate}, '
        f'found bug: {self.found_bug}, '
        f'max coverage: {self.max_coverage}, '
        f'max line coverage diff: {self.max_line_coverage_diff}\n'
        f'max coverage sample: {self.max_coverage_sample}\n'
        f'max coverage diff sample: {self.max_coverage_diff_sample}\n'
        f'max coverage diff report: {self.max_coverage_diff_report or "None"}')

  @classmethod
  def from_experiment_result(
      cls, sample_results: list[ExperimentResult]) -> 'AggregatedResult':
    """Aggereate experiment history results of all samples."""
    if not sample_results:
      return AggregatedResult()
    sample_final_build_results = [[
        result
        for result in sample_result_history.history_results
        if isinstance(result, BuildResult)
    ][-1]
                                  for sample_result_history in sample_results]
    build_success_rate = sum([
        int(sample_final_result.status)
        for sample_final_result in sample_final_build_results
    ]) / len(sample_final_build_results)
    return AggregatedResult(build_success_rate=build_success_rate,)


def generate_targets(benchmark: Benchmark, model: models.LLM,
                     prompt: prompts.Prompt, work_dirs: WorkDirs,
                     builder: prompt_builder.PromptBuilder) -> list[str]:
  """Generates fuzz target with LLM."""
  logger.info('Generating targets for %s %s using %s..', benchmark.project,
              benchmark.function_signature, model.name)
  model.query_llm(prompt, response_dir=work_dirs.raw_targets)

  _, target_ext = os.path.splitext(benchmark.target_path)
  generated_targets = []
  for file in os.listdir(work_dirs.raw_targets):
    if not output_parser.is_raw_output(file):
      continue
    raw_output = os.path.join(work_dirs.raw_targets, file)
    target_code = output_parser.parse_code(raw_output)
    target_code = builder.post_process_generated_code(target_code)
    target_id, _ = os.path.splitext(raw_output)
    target_file = f'{target_id}{target_ext}'
    target_path = os.path.join(work_dirs.raw_targets, target_file)
    output_parser.save_output(target_code, target_path)
    generated_targets.append(target_path)

  if generated_targets:
    targets_relpath = map(os.path.relpath, generated_targets)
    targets_relpath_str = '\n '.join(targets_relpath)
    logger.info('Generated:\n %s', targets_relpath_str)
  else:
    logger.info('Failed to generate targets: %s', generated_targets)
  return generated_targets


def aggregate_results(target_stats: list[tuple[int, exp_evaluator.Result]],
                      generated_targets: list[str]) -> AggregatedResult:
  """Aggregates experiment status and results of a targets."""
  build_success_rate = sum([int(stat.compiles) for _, stat in target_stats
                           ]) / len(target_stats)
  crash_rate = sum([int(stat.crashes) for _, stat in target_stats
                   ]) / len(target_stats)
  found_bug = sum([
      int(stat.crashes and not stat.is_semantic_error)
      for _, stat in target_stats
  ])
  max_coverage = max([stat.coverage for _, stat in target_stats])
  max_line_coverage_diff = max(
      [stat.line_coverage_diff for _, stat in target_stats])

  max_coverage_sample = ''
  max_coverage_diff_sample = ''
  max_coverage_diff_report = ''

  all_textcov = textcov.Textcov()
  for i, stat in target_stats:
    if stat.coverage == max_coverage:
      max_coverage_sample = generated_targets[i]

    if stat.line_coverage_diff == max_line_coverage_diff:
      max_coverage_diff_sample = generated_targets[i]
      max_coverage_diff_report = stat.coverage_report_path

    if isinstance(stat.textcov_diff, textcov.Textcov):
      all_textcov.merge(stat.textcov_diff)

  return AggregatedResult(build_success_rate, crash_rate, found_bug,
                          max_coverage, max_line_coverage_diff,
                          max_coverage_sample, max_coverage_diff_sample,
                          max_coverage_diff_report, all_textcov)


def check_targets(
    ai_binary: str,
    benchmark: Benchmark,
    work_dirs: WorkDirs,
    generated_targets: List[str],
    cloud_experiment_name: str = '',
    cloud_experiment_bucket: str = '',
    run_timeout: int = RUN_TIMEOUT,
    fixer_model_name: str = models.DefaultModel.name,
) -> Optional[AggregatedResult]:
  """Builds all targets in the fixed target directory."""
  target_stats = []

  if cloud_experiment_name:
    builder_runner = builder_runner_lib.CloudBuilderRunner(
        benchmark,
        work_dirs,
        run_timeout,
        fixer_model_name,
        experiment_name=cloud_experiment_name,
        experiment_bucket=cloud_experiment_bucket,
    )
  else:
    builder_runner = builder_runner_lib.BuilderRunner(benchmark, work_dirs,
                                                      run_timeout,
                                                      fixer_model_name)

  evaluator = exp_evaluator.Evaluator(builder_runner, benchmark, work_dirs)

  ai_target_pairs = [(ai_binary, target) for target in generated_targets]
  with pool.ThreadPool(NUM_EVA) as p:
    for i, target_stat in enumerate(
        p.starmap(evaluator.check_target, ai_target_pairs)):
      if target_stat is None:
        logger.error('This should never happen: Error evaluating target: %s',
                     generated_targets[i])
        target_stat = exp_evaluator.Result()

      target_stats.append((i, target_stat))

  if len(target_stats) > 0:
    return aggregate_results(target_stats, generated_targets)

  logger.info('No targets to check.')
  return None


def prepare(oss_fuzz_dir: str) -> None:
  """Prepares the experiment environment."""
  oss_fuzz_checkout.clone_oss_fuzz(oss_fuzz_dir)
  oss_fuzz_checkout.postprocess_oss_fuzz()


def initialize_thread(index):
  """Initialize thread-local storage for each thread."""
  # Thread-local storage object
  thread_local.index = index
  # Initialize more complex objects or variables if needed
  print(f"Initialized thread-local storage for index={index}")


### copied from run_all_experiments.py
def _print_and_dump_experiment_result(result: Result, save_dir):
  """Prints the |result| of a single experiment."""
  logger.info('\n**** Finished benchmark %s, %s ****\n%s',
              result.benchmark.project, result.benchmark.function_signature,
              result.result)

  EXPERIMENT_RESULTS.append(result)

  # Process total gain from all generated harnesses for each projects and
  # update summary report. This makes it possible to view per-project stats
  # as experiments complete rather than only after all experiments run.
  coverage_gain_dict = _process_total_coverage_gain(EXPERIMENT_RESULTS)
  add_to_json_report(save_dir, 'project_summary', coverage_gain_dict)


JSON_REPORT = 'report.json'
import json


def add_to_json_report(outdir: str, key: str, value: Any) -> None:
  """Adds a key/value pair to JSON report."""
  os.makedirs(outdir, exist_ok=True)
  json_report_path = os.path.join(outdir, JSON_REPORT)
  if os.path.isfile(json_report_path):
    with open(json_report_path, 'r') as f:
      json_report = json.load(f)
  else:
    json_report = {}

  json_report[key] = value

  # Overwrite the new json file
  with open(json_report_path, 'w') as f:
    f.write(json.dumps(json_report))


def _process_total_coverage_gain(
    results: list[Result]) -> dict[str, dict[str, Any]]:
  """Processes and calculates the total coverage gain for each project."""
  textcov_dict: dict[str, list[textcov.Textcov]] = {}
  if not results:
    return {}
  for result in results:
    # TODO(dongge): Do not use a hacky string for result.result when an
    # exception happened during experiments?
    if not isinstance(result.result, AggregatedResult):
      continue
    cov = result.result.full_textcov_diff
    if not cov:
      continue
    if result.benchmark.project not in textcov_dict:
      textcov_dict[result.benchmark.project] = []
    textcov_dict[result.benchmark.project].append(cov)

  coverage_gain: dict[str, dict[str, Any]] = {}
  for project, cov_list in textcov_dict.items():
    total_cov = textcov.Textcov()
    for cov in cov_list:
      total_cov.merge(cov)

    coverage_summary = run_all_experiments.evaluator.load_existing_coverage_summary(
        project)

    try:
      coverage_summary_files = coverage_summary['data'][0]['files']
      lines = [f['summary']['lines']['count'] for f in coverage_summary_files]
    except KeyError:
      lines = []

    total_lines = max(total_cov.total_lines, sum(lines))

    if total_lines:
      coverage_gain[project] = {
          'coverage_diff': total_cov.covered_lines / total_lines
      }
    else:
      # Fail safe when total_lines is 0 because of invalid coverage report
      logger.warning(
          'Line coverage information missing from the coverage report.')
      coverage_gain[project] = {'coverage_diff': 0.0}

  return coverage_gain


if __name__ == '__main__':

  prepare('')

  model = models.LLM.setup(ai_binary='',
                           name='gpt-4o-azure',
                           max_tokens=MAX_TOKENS,
                           num_samples=NUM_SAMPLES,
                           temperature=TEMPERATURE)
  benchmarks_all = Benchmark.from_yaml(
      'benchmark-sets/spec_test/libmodbus.yaml')

  report_dir = 'results/output-libmodbus-modbus_write_bits/fixed_targets'

  benchmarks = []
  # print all benchmark names
  for benchmark in benchmarks_all:
    if benchmark.id == 'libmodbus-modbus_write_bits':
      benchmarks.append(benchmark)

  # # backup work_dirs by copying to a new directory
  # if os.path.exists(RESULTS_DIR):
  #   shutil.copytree(RESULTS_DIR, f'{RESULTS_DIR}_backup')  # backup all results

  work_dirs = WorkDirs(f'{RESULTS_DIR}', keep=True)

  generated_targets = []
  for file in os.listdir(
      report_dir):  # copy all generated targets to fixed_targets directory
    if file.endswith('.c'):
      generated_targets.append(os.path.join(report_dir, file))

  global EXPERIMENT_RESULTS
  EXPERIMENT_RESULTS = []

  for benchmark in benchmarks:
    print(benchmark)
    print("*" * 50)
    result = check_targets(ai_binary='',
                           benchmark=benchmark,
                           work_dirs=work_dirs,
                           generated_targets=generated_targets,
                           cloud_experiment_name='',
                           cloud_experiment_bucket='',
                           run_timeout=RUN_TIMEOUT,
                           fixer_model_name='gpt-4o-azure')
    # break
    res = Result(benchmark, result, work_dirs)
    import run_all_experiments
    _print_and_dump_experiment_result(res, report_dir)
    # Process total gain from all generated harnesses for each projects
    coverage_gain_dict = _process_total_coverage_gain(EXPERIMENT_RESULTS)
    add_to_json_report(report_dir, 'project_summary', coverage_gain_dict)

    run_all_experiments._print_experiment_results(EXPERIMENT_RESULTS,
                                                  coverage_gain_dict)
