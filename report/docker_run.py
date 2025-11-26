"""
Usage:
  docker_run.py [options]
"""

import argparse
import datetime
import logging
import os
import subprocess
import sys

from llm_toolkit import models
import run_single_fuzz

# Configure logging to display all messages at or above INFO level
logging.basicConfig(level=logging.INFO)

BENCHMARK_SET = 'comparison'
RUN_TIMEOUT = run_single_fuzz.RUN_TIMEOUT
MODEL = models.DefaultModel.name
DELAY = 0
NUM_SAMPLES = run_single_fuzz.NUM_SAMPLES
MAX_ROUND = 10
TEMPERATURE = run_single_fuzz.TEMPERATURE
WORK_DIR = run_single_fuzz.RESULTS_DIR
DATA_DIR = '/experiment/data-dir/'

def _parse_args(cmd) -> argparse.Namespace:
  """Parses the command line arguments."""
  parser = argparse.ArgumentParser(description='Run experiments')
  parser.add_argument(
      '-b',
      '--benchmark-set',
      type=str,
      default=BENCHMARK_SET,
      help=f'Experiment benchmark set, default: {BENCHMARK_SET}.')
  parser.add_argument(
      '-to',
      '--run-timeout',
      type=int,
      default=RUN_TIMEOUT,
      help=f'Fuzzing timeout in seconds, default: {RUN_TIMEOUT} seconds.')
  parser.add_argument('-m',
                      '--model',
                      type=str,
                      default=MODEL,
                      help=f'Large Language Model name, default: {MODEL}.')
  parser.add_argument(
      '-d',
      '--delay',
      type=int,
      default=DELAY,
      help=f'Delay each benchmark experiment by N seconds, default: {DELAY}.')
  parser.add_argument(
      '-w',
      '--work-dir',
      type=str,
      default=WORK_DIR,
      help=f'Path to store experiment outputs, default: {WORK_DIR}.')
  parser.add_argument(
      '-i',
      '--local-introspector',
      type=str,
      default="false",
      help=
      'If set to "true" will use a local version of fuzz introspector\'s webapp'
  )
  parser.add_argument(
      '-ns',
      '--num-samples',
      type=int,
      default=NUM_SAMPLES,
      help=f'The number of samples to request from LLM, default: {NUM_SAMPLES}')
  parser.add_argument(
      '-t',
      '--temperature',
      type=float,
      default=TEMPERATURE,
      help='Temperature to use for samples, default matches run_logicfuzz.')
  parser.add_argument(
      '-tr',
      '--temperature-list',
      nargs='*',
      type=float,
      default=[],
      help='Optional list of temperatures to cycle through for samples.')
  parser.add_argument(
      '-bd',
      '--benchmarks-directory',
      type=str,
      help='Path to benchmark directory. Defaults to conti benchmark set.')
  # Note: Agent mode (LangGraph) is now the default and only mode.
  # The --agent flag has been removed.
  parser.add_argument('-mr',
                      '--max-round',
                      type=int,
                      default=MAX_ROUND,
                      help=f'Max trial round for agents, default: {MAX_ROUND}.')
  parser.add_argument(
      '-rd',
      '--redirect-outs',
      type=str,
      default="false",
      help=
      'Redirects experiments stdout/stderr to file. Set to "true" to enable.')
  args, additional_args = parser.parse_known_args(cmd)

  # Arguments after the first element ("--") separator.
  if additional_args and additional_args[0] == '--':
    args.additional_args = additional_args[1:]
  else:
    args.additional_args = additional_args

  # Parse boolean arguments
  args.local_introspector = args.local_introspector.lower() == "true"
  args.redirect_outs = args.redirect_outs.lower() == "true"

  return args

def _run_command(command: list[str], shell=False):
  """Runs a command and return its exit code."""
  process = subprocess.run(command, shell=shell, check=False)
  return process.returncode

def _log_common_args(args):
  """Prints args useful for logging"""
  logging.info("Benchmark set is %s.", args.benchmark_set)
  logging.info("Run timeout is %s.", args.run_timeout)
  logging.info("LLM is %s.", args.model)
  logging.info("DELAY is %s.", args.delay)
  logging.info("Work dir is %s.", args.work_dir)

def main(cmd=None):
  """Main entrypoint"""
  if os.path.isfile('/experiment/data-dir.zip'):
    subprocess.check_call(
        'apt-get install -y zip && zip -s0 data-dir.zip --out newd.zip && unzip newd.zip && rm ./data-dir.z*',
        shell=True,
        cwd='/experiment')
  if os.path.isdir(DATA_DIR):
    run_on_data_from_scratch(cmd)
  else:
    run_standard(cmd)

def run_on_data_from_scratch(cmd=None):
  """Creates experiment for projects that are not in OSS-Fuzz upstream"""
  args = _parse_args(cmd)

  # Uses python3 by default and /venv/bin/python3 for Docker containers.
  python_path = "/venv/bin/python3" if os.path.exists(
      "/venv/bin/python3") else "python3"
  os.environ["PYTHON"] = python_path

  _log_common_args(args)

  # Launch starter, which set ups a Fuzz Introspector instance, which
  # will be used for creating benchmarks and extract context.
  logging.info('Running starter script')
  subprocess.check_call('/experiment/report/custom_oss_fuzz_fi_starter.sh',
                        shell=True)

  date = datetime.datetime.now().strftime('%Y-%m-%d')
  benchmark_label = args.benchmarks_directory or args.benchmark_set
  experiment_name = f"{date}-{benchmark_label}"
  report_label = experiment_name
  logging.info("Report label is %s.", report_label)

  local_results_dir = args.work_dir

  # Generate a report locally
  upload_env = os.environ.copy()
  upload_env["REPORT_LABEL"] = report_label
  report_process = subprocess.Popen([
      "bash", "report/upload_report.sh", local_results_dir, benchmark_label,
      args.model
  ] + args.additional_args,
                                     env=upload_env)

  # Launch run_logicfuzz.py
  # some notes:
  # - we will generate benchmarks using the local FI running
  # - we will use the oss-fuzz project of our workdir, which is
  #   the only one that has the projets.
  environ = os.environ.copy()

  # We need to make sure that we use our version of OSS-Fuzz
  environ['OSS_FUZZ_DATA_DIR'] = os.path.join(DATA_DIR, 'oss-fuzz2')

  # Get project names to analyse
  project_in_oss_fuzz = []
  for project_name in os.listdir(
      os.path.join(DATA_DIR, 'oss-fuzz2', 'build', 'out')):
    project_path = os.path.join(DATA_DIR, 'oss-fuzz2', 'build', 'out',
                                project_name)
    if not os.path.isdir(project_path):
      continue
    project_in_oss_fuzz.append(project_name)
  project_names = ','.join(project_in_oss_fuzz)

  introspector_endpoint = "http://127.0.0.1:8080/api"

  cmd = [python_path, 'run_logicfuzz.py']
  cmd.append('-g')
  cmd.append(
      'far-reach-low-coverage,low-cov-with-fuzz-keyword,easy-params-far-reach')
  cmd.append('-gp')
  cmd.append(project_names)
  cmd.append('-gm')
  cmd.append(str(8))
  cmd.append('-e')
  cmd.append(introspector_endpoint)
  cmd.append('-mr')
  cmd.append(str(args.max_round))
  cmd += [
      "--run-timeout",
      str(args.run_timeout), "--work-dir",
      local_results_dir, "--num-samples",
      str(args.num_samples), "--delay",
      str(args.delay), "--context", "--model", args.model, "--temperature",
      str(args.temperature)
  ]
  if args.temperature_list:
    cmd.append("--temperature-list")
    cmd.extend(str(temp) for temp in args.temperature_list)
  if args.additional_args:
    cmd.extend(args.additional_args)
  # Note: Agent mode is now the default, no need to append --agent flag

  # Run the experiment and redirect to file if indicated.
  if args.redirect_outs:
    with open(f"{local_results_dir}/logs-from-run.txt", "w") as outfile:
      process = subprocess.run(cmd,
                               stdout=outfile,
                               stderr=outfile,
                               env=environ,
                               check=False)
      ret_val = process.returncode
  else:
    process = subprocess.run(cmd, env=environ, check=False)
    ret_val = process.returncode

  os.environ["ret_val"] = str(ret_val)

  with open("/experiment_ended", "w"):
    pass

  logging.info("Shutting down introspector")
  try:
    subprocess.run(["curl", "--silent", "http://localhost:8080/api/shutdown"],
                   check=False,
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
  except Exception:
    pass

  # Wait for the report process to finish writing locally.
  report_process.wait()

  # Exit with the return value of `./run_logicfuzz`.
  return ret_val

def run_standard(cmd=None):
  """The main function."""
  args = _parse_args(cmd)

  # Uses python3 by default and /venv/bin/python3 for Docker containers.
  python_path = "/venv/bin/python3" if os.path.exists(
      "/venv/bin/python3") else "python3"
  os.environ["PYTHON"] = python_path

  _log_common_args(args)

  if args.local_introspector:
    os.environ["BENCHMARK_SET"] = args.benchmark_set
    introspector_endpoint = "http://127.0.0.1:8080/api"
    logging.info("LOCAL_INTROSPECTOR is enabled: %s", introspector_endpoint)
    _run_command(['bash', 'report/launch_local_introspector.sh'], shell=True)
  else:
    introspector_endpoint = "https://introspector.oss-fuzz.com/api"
    logging.info("LOCAL_INTROSPECTOR was not specified. Defaulting to %s.",
                 introspector_endpoint)

  logging.info("NUM_SAMPLES is %s.", args.num_samples)

  date = datetime.datetime.now().strftime('%Y-%m-%d')
  local_results_dir = args.work_dir
  benchmark_label = args.benchmarks_directory or args.benchmark_set

  experiment_name = f"{date}-{benchmark_label}"
  report_label = experiment_name
  logging.info("Report label is %s.", report_label)

  # Generate a report locally
  upload_env = os.environ.copy()
  upload_env["REPORT_LABEL"] = report_label
  report_process = subprocess.Popen([
      "bash", "report/upload_report.sh", local_results_dir, benchmark_label,
      args.model
  ] + args.additional_args,
                                     env=upload_env)

  # Prepare the command to run experiments
  benchmark_directory = (args.benchmarks_directory or
                         f"conti-benchmark/{args.benchmark_set}")
  run_cmd = [
      python_path, "run_logicfuzz.py", "--benchmarks-directory",
      benchmark_directory, "--run-timeout",
      str(args.run_timeout), "--work-dir",
      local_results_dir, "--num-samples",
      str(args.num_samples), "--delay",
      str(args.delay), "--context", "--introspector-endpoint",
      introspector_endpoint, "--model", args.model, "--max-round",
      str(args.max_round), "--temperature",
      str(args.temperature)
  ]
  if args.temperature_list:
    run_cmd.append("--temperature-list")
    run_cmd.extend(str(temp) for temp in args.temperature_list)
  # Note: Agent mode is now the default, no need to append --agent flag

  if args.additional_args:
    run_cmd.extend(args.additional_args)

  # Run the experiment and redirect to file if indicated.
  if args.redirect_outs:
    with open(f"{local_results_dir}/logs-from-run.txt", "w") as outfile:
      process = subprocess.run(run_cmd,
                               stdout=outfile,
                               stderr=outfile,
                               check=False)
      ret_val = process.returncode
  else:
    process = subprocess.run(run_cmd, check=False)
    ret_val = process.returncode

  os.environ["ret_val"] = str(ret_val)

  with open("/experiment_ended", "w"):
    pass

  if args.local_introspector:
    logging.info("Shutting down introspector")
    try:
      subprocess.run(["curl", "--silent", "http://localhost:8080/api/shutdown"],
                     check=False,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    except Exception:
      pass

  # Wait for the report process to finish writing locally.
  report_process.wait()

  # Exit with the return value of `./run_logicfuzz`.
  return ret_val

if __name__ == "__main__":
  sys.exit(main())
# /venv/bin/python3 run_logicfuzz.py -l gpt-5 -y conti-benchmark/cjson.yaml
