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
This script is used to run benchmarks and report results in a Docker container.
"""
import argparse
import datetime
import os
import subprocess
import sys


def main(benchmark_set, frequency_label, run_timeout, sub_dir, model, delay):
  # Determine the appropriate Python executable for use in Docker containers
  python_executable = "/venv/bin/python3" if os.path.exists(
      "/venv/bin/python3") else "python3"

  # If the GOOGLE_APPLICATION_CREDENTIALS environment variable is set,
  # activate the service account for Google Cloud interactions
  google_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
  if google_credentials:
    subprocess.run([
        'gcloud', 'auth', 'activate-service-account',
        'LLM-EVAL@oss-fuzz.iam.gserviceaccount.com', '--key-file',
        google_credentials
    ],
                   check=True)

  # Set default values for optional arguments if not specified by the user
  benchmark_set = benchmark_set or 'comparison'
  frequency_label = frequency_label or 'daily'
  run_timeout = run_timeout or 300
  sub_dir = sub_dir or 'default'
  model = model or 'vertex_ai_code-bison-32k'
  delay = delay or 0

  # Construct experiment name and directories based on current date,
  # frequency, and benchmark set
  date_today = datetime.datetime.now().strftime('%Y-%m-%d')
  local_results_dir = 'results'
  experiment_name = f"{date_today}-{frequency_label}-{benchmark_set}"
  gcs_report_dir = f"{sub_dir}/{experiment_name}"

  # Start the report upload in a separate process
  report_process = subprocess.Popen([
      'bash', 'report/upload_report.sh', local_results_dir, gcs_report_dir,
      benchmark_set, model
  ])

  # Execute the experiment using the specified configuration
  ret_val = subprocess.run([
      python_executable, 'run_all_experiments.py', '--benchmarks-directory',
      f"benchmark-sets/{benchmark_set}", '--run-timeout',
      str(run_timeout), '--cloud-experiment-name', experiment_name,
      '--cloud-experiment-bucket', 'oss-fuzz-gcb-experiment-run-logs',
      '--template-directory', 'prompts/template_xml', '--work-dir',
      local_results_dir, '--num-samples', '10', '--delay',
      str(delay), '--model', model
  ],
                           check=True).returncode

  # Signal the end of the experiment

  with open('/experiment_ended', 'a'):
    os.utime('/experiment_ended', None)

  # Ensure the report process completes before exiting
  report_process.wait()

  sys.exit(ret_val)  # Use sys.exit to terminate the script properly


if __name__ == '__main__':
  # Set up the command-line argument parser
  parser = argparse.ArgumentParser(
      description="Run benchmarks and report results.")
  parser.add_argument('benchmark_set',
                      nargs='?',
                      default='comparison',
                      help='Set of benchmarks used for the experiment')
  parser.add_argument(
      'frequency_label',
      nargs='?',
      default='daily',
      help='Frequency label for Cloud Build tags and directories')
  parser.add_argument('run_timeout',
                      nargs='?',
                      default=300,
                      type=int,
                      help='Timeout in seconds for each fuzzing target')
  parser.add_argument('sub_dir',
                      nargs='?',
                      default='default',
                      help='Sub-directory for storing reports')
  parser.add_argument('model',
                      nargs='?',
                      default='vertex_ai_code-bison-32k',
                      help='Language model used for generating fuzz targets')
  parser.add_argument('delay',
                      nargs='?',
                      default=0,
                      type=int,
                      help='Delay to amortize quota usage')
  args = parser.parse_args()

  # Execute the main function with the parsed arguments
  main(args.benchmark_set, args.frequency_label, args.run_timeout, args.sub_dir,
       args.model, args.delay)
