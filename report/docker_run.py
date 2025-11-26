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
from typing import List

import run_logicfuzz
from llm_toolkit import models
import run_single_fuzz

# Configure logging to display all messages at or above INFO level
logging.basicConfig(level=logging.INFO)

BENCHMARK_SET = 'comparison'
DATA_DIR = '/experiment/data-dir/'

def _needs_benchmark_selection(cmd: List[str]) -> bool:
  """Returns True if user did not pass any benchmark selector flag."""
  benchmark_flags = {
      "-y", "--benchmark-yaml", "-b", "--benchmarks-directory", "-g",
      "--generate-benchmarks"
  }
  return not any(token in benchmark_flags for token in cmd)


def _parse_args(cmd) -> argparse.Namespace:
  """Parses docker-specific arguments and forwards the rest."""
  parser = argparse.ArgumentParser(
      description=("Wrapper around run_logicfuzz.py. All unrecognized flags "
                   "are forwarded directly to run_logicfuzz.py."))
  parser.add_argument(
      '-i',
      '--local-introspector',
      type=str,
      default="true",
      help=('Controls the bundled local Fuzz Introspector (default: "true"). '
            'Set to "false" only if you already run one on localhost:8080.'))
  parser.add_argument(
      '-rd',
      '--redirect-outs',
      type=str,
      default="false",
      help=
      'Redirects experiments stdout/stderr to file. Set to "true" to enable.')
  args, run_logicfuzz_args = parser.parse_known_args(cmd)

  run_logicfuzz_args = list(run_logicfuzz_args)
  if _needs_benchmark_selection(run_logicfuzz_args):
    default_dir = os.path.join("conti-benchmark", BENCHMARK_SET)
    logging.info(
        "No benchmark selector provided; defaulting to '--benchmarks-directory %s'.",
        default_dir)
    run_logicfuzz_args.extend(["--benchmarks-directory", default_dir])

  args.local_introspector = args.local_introspector.lower() == "true"
  args.redirect_outs = args.redirect_outs.lower() == "true"
  args.run_logicfuzz_args = run_logicfuzz_args

  return args

def _run_command(command: list[str], shell=False):
  """Runs a command and return its exit code."""
  process = subprocess.run(command, shell=shell, check=False)
  return process.returncode

def _log_common_args(args):
  """Prints args useful for logging."""
  benchmark_source = (args.benchmark_yaml or args.benchmarks_directory or
                      f"generated({args.generate_benchmarks})")
  logging.info("Benchmark source is %s.", benchmark_source)
  logging.info("Run timeout is %s.", args.run_timeout)
  logging.info("LLM is %s.", args.model)
  logging.info("DELAY is %s.", args.delay)
  logging.info("Work dir is %s.", args.work_dir)


def _derive_benchmark_label(args: argparse.Namespace) -> str:
  """Returns a short label for reports/introspector env."""
  if args.benchmark_yaml:
    return os.path.splitext(os.path.basename(args.benchmark_yaml))[0]
  if args.benchmarks_directory:
    return os.path.basename(os.path.normpath(args.benchmarks_directory))
  if args.generate_benchmarks_projects:
    return args.generate_benchmarks_projects.replace(',', '_')
  if args.generate_benchmarks:
    return args.generate_benchmarks.replace(',', '_')
  return BENCHMARK_SET

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
  run_args = run_logicfuzz.parse_args(args.run_logicfuzz_args)

  # Uses python3 by default and /venv/bin/python3 for Docker containers.
  python_path = "/venv/bin/python3" if os.path.exists(
      "/venv/bin/python3") else "python3"
  os.environ["PYTHON"] = python_path

  _log_common_args(run_args)

  # Launch starter, which set ups a Fuzz Introspector instance, which
  # will be used for creating benchmarks and extract context.
  logging.info('Running starter script')
  subprocess.check_call('/experiment/report/custom_oss_fuzz_fi_starter.sh',
                        shell=True)

  date = datetime.datetime.now().strftime('%Y-%m-%d')
  benchmark_label = _derive_benchmark_label(run_args)
  experiment_name = f"{date}-{benchmark_label}"
  report_label = experiment_name
  logging.info("Report label is %s.", report_label)

  local_results_dir = run_args.work_dir

  # Generate a report locally
  upload_env = os.environ.copy()
  upload_env["REPORT_LABEL"] = report_label
  report_process = subprocess.Popen([
      "bash", "report/upload_report.sh", local_results_dir, benchmark_label,
      run_args.model
  ] + args.run_logicfuzz_args,
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
  cmd.append(str(run_args.max_round))
  cmd += [
      "--run-timeout",
      str(run_args.run_timeout), "--work-dir",
      local_results_dir, "--num-samples",
      str(run_args.num_samples), "--delay",
      str(run_args.delay), "--context", "--model", run_args.model,
      "--temperature",
      str(run_args.temperature)
  ]
  if run_args.temperature_list:
    cmd.append("--temperature-list")
    cmd.extend(str(temp) for temp in run_args.temperature_list)
  if args.run_logicfuzz_args:
    cmd.extend(args.run_logicfuzz_args)
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
  run_args = run_logicfuzz.parse_args(args.run_logicfuzz_args)

  # Uses python3 by default and /venv/bin/python3 for Docker containers.
  python_path = "/venv/bin/python3" if os.path.exists(
      "/venv/bin/python3") else "python3"
  os.environ["PYTHON"] = python_path

  _log_common_args(run_args)

  introspector_endpoint = run_args.introspector_endpoint
  benchmark_label = _derive_benchmark_label(run_args)
  if args.local_introspector:
    os.environ["BENCHMARK_SET"] = benchmark_label
    logging.info("LOCAL_INTROSPECTOR is enabled: %s", introspector_endpoint)
    _run_command(['bash', 'report/launch_local_introspector.sh'], shell=True)
  else:
    logging.info(
        "LOCAL_INTROSPECTOR auto-launch disabled; expecting service at %s.",
        introspector_endpoint)

  logging.info("NUM_SAMPLES is %s.", run_args.num_samples)

  date = datetime.datetime.now().strftime('%Y-%m-%d')
  local_results_dir = run_args.work_dir

  experiment_name = f"{date}-{benchmark_label}"
  report_label = experiment_name
  logging.info("Report label is %s.", report_label)

  # Generate a report locally
  upload_env = os.environ.copy()
  upload_env["REPORT_LABEL"] = report_label
  report_process = subprocess.Popen([
      "bash", "report/upload_report.sh", local_results_dir, benchmark_label,
      run_args.model
  ] + args.run_logicfuzz_args,
                                     env=upload_env)

  # Prepare the command to run experiments
  run_cmd = [python_path, "run_logicfuzz.py"] + args.run_logicfuzz_args

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
