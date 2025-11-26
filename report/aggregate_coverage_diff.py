#!/usr/bin/env python3

# This generates a per-PROJECT coverage diff (as opposed to the default
# per-benchmark).
# Usage: curl http://localhost:PORT/json | python aggregate_coverage_diff.py
# (where http://localhost:PORT comes from `python web.py <results-dir> <port>`)

import json
import logging
import os
import sys
import traceback

from experiment import evaluator, textcov

def _iter_textcov_files(textcov_root: str):
  """Yield all textcov report file paths under |textcov_root|."""
  if not os.path.isdir(textcov_root):
    logging.warning('Missing textcov reports at %s', textcov_root)
    return

  for dirpath, _, filenames in os.walk(textcov_root):
    for filename in filenames:
      yield os.path.join(dirpath, filename)


def compute_coverage_diff(project: str, coverage_links: list[str]):
  existing_textcov = evaluator.load_existing_textcov(project)
  coverage_summary = evaluator.load_existing_coverage_summary(project)

  new_textcov = textcov.Textcov()

  for coverage_link in coverage_links:
    if coverage_link.startswith('gs://'):
      logging.warning('Skipping remote coverage report %s; GCS is unsupported.',
                      coverage_link)
      continue

    textcov_root = os.path.join(coverage_link, 'textcov_reports')
    for report_path in _iter_textcov_files(textcov_root):
      logging.info('Loading %s', report_path)
      with open(report_path, 'r', encoding='utf-8') as f:
        try:
        new_textcov.merge(textcov.Textcov.from_file(f))
        except Exception:
          logging.warning('Failed to load %s', report_path)

  new_textcov.subtract_covered_lines(existing_textcov)
  try:
    total_lines = coverage_summary['data'][0]['totals']['lines']['count']
  except KeyError:
    total_lines = 1

  return new_textcov.covered_lines / total_lines
  #print(f'{project}:', new_textcov.covered_lines / total_lines)

def main():
  logging.basicConfig(level=logging.INFO)

  project_coverages = {}

  data = json.load(sys.stdin)
  for benchmark in data['benchmarks']:
    # TODO(ochang): Properly store the project, as projects can have '-' in the name.
    project = benchmark['benchmark'].split('-')[1]
    report = benchmark.get('max_line_coverage_diff_report')
    if report:
      project_coverages.setdefault(project, []).append(report)

  diffs = {}
  for project, coverage_links in project_coverages.items():
    logging.info('Computing coverage diff for %s', project)
    try:
      diffs[project] = compute_coverage_diff(project, coverage_links)
    except Exception:
      logging.error('Failed to compute coverage for %s', project)
      traceback.print_exc()

  print(diffs)

if __name__ == '__main__':
  main()
