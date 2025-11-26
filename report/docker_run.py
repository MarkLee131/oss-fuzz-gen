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

BENCHMARK_SET = 'conti-benchmark'
DATA_DIR = '/experiment/data-dir/'
DEFAULT_BENCHMARK_DIR = 'conti-benchmark'

def _needs_benchmark_selection(cmd: List[str]) -> bool:
  """Returns True if user did not pass any benchmark selector flag."""
  benchmark_flags = {
      "-y", "--benchmark-yaml", "-b", "--benchmarks-directory", "-g",
      "--generate-benchmarks"
  }
  return not any(token in benchmark_flags for token in cmd)


def _parse_args(cmd) -> argparse.Namespace:
  """Parses docker-specific arguments and forwards the rest."""
  if cmd is None:
    cmd = sys.argv[1:]
  cmd = list(cmd)

  additional_args = []
  if '--' in cmd:
    separator_index = cmd.index('--')
    additional_args = cmd[separator_index + 1:]
    cmd = cmd[:separator_index]

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
  args.additional_args = additional_args

  # Parse boolean arguments
  args.local_introspector = args.local_introspector.lower() == "true"
  args.redirect_outs = args.redirect_outs.lower() == "true"
  args.run_logicfuzz_args = run_logicfuzz_args

  if _needs_benchmark_selection(args.run_logicfuzz_args):
    logging.info("No benchmark flag detected, defaulting to %s.",
                 DEFAULT_BENCHMARK_DIR)
    args.run_logicfuzz_args = ['-b', DEFAULT_BENCHMARK_DIR
                               ] + args.run_logicfuzz_args

  return args


def _resolve_python_path() -> str:
  """Detects python path and exports it via PYTHON."""
  python_path = "/venv/bin/python3" if os.path.exists(
      "/venv/bin/python3") else "python3"
  os.environ["PYTHON"] = python_path
  return python_path


def _run_logicfuzz_command(cmd: list[str], redirect_outs: bool,
                           local_results_dir: str, env: dict | None = None):
  """Runs LogicFuzz with optional stdout/stderr redirection."""
  if redirect_outs:
    with open(f"{local_results_dir}/logs-from-run.txt", "w") as outfile:
      process = subprocess.run(cmd,
                               stdout=outfile,
                               stderr=outfile,
                               env=env,
                               check=False)
      return process.returncode
  process = subprocess.run(cmd, env=env, check=False)
  return process.returncode


def _collect_projects(data_dir: str) -> str:
  """Discovers OSS-Fuzz builds in data directory."""
  projects_root = os.path.join(data_dir, 'build', 'out')
  if not os.path.isdir(projects_root):
    logging.warning("No projects found under %s.", projects_root)
    return ''
  project_names = [
      project_name for project_name in os.listdir(projects_root)
      if os.path.isdir(os.path.join(projects_root, project_name))
  ]
  return ','.join(sorted(project_names))


def _build_data_mode_cmd(python_path: str, run_args: argparse.Namespace,
                         project_names: str, introspector_endpoint: str,
                         passthrough_args: list[str]) -> list[str]:
  """Assembles command for non-OSS-Fuzz data-dir runs."""
  cmd = [python_path, 'run_logicfuzz.py', '-g']
  cmd.append(
      'far-reach-low-coverage,low-cov-with-fuzz-keyword,easy-params-far-reach')
  cmd.extend(['-gp', project_names or ''])
  cmd.extend(['-gm', str(8)])
  cmd.extend(['-e', introspector_endpoint])
  cmd.extend(['-mr', str(run_args.max_round)])
  cmd += [
      "--run-timeout",
      str(run_args.run_timeout), "--work-dir",
      run_args.work_dir, "--num-samples",
      str(run_args.num_samples), "--delay",
      str(run_args.delay), "--context", "--model", run_args.model,
      "--temperature",
      str(run_args.temperature)
  ]
  if run_args.temperature_list:
    cmd.append("--temperature-list")
    cmd.extend(str(temp) for temp in run_args.temperature_list)
  if passthrough_args:
    cmd.extend(passthrough_args)
  return cmd

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
  if os.path.isdir(DATA_DIR):
    run_on_data_from_scratch(cmd)
  else:
    run_standard(cmd)

def run_on_data_from_scratch(cmd=None):
  """Creates experiment for projects that are not in OSS-Fuzz upstream"""
  args = _parse_args(cmd)
  run_args = run_logicfuzz.parse_args(args.run_logicfuzz_args)

  python_path = _resolve_python_path()
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

  environ = os.environ.copy()
  environ['OSS_FUZZ_DATA_DIR'] = os.path.join(DATA_DIR, 'oss-fuzz2')
  project_names = _collect_projects(environ['OSS_FUZZ_DATA_DIR'])
  introspector_endpoint = "http://127.0.0.1:8080/api"
  logicfuzz_cmd = _build_data_mode_cmd(python_path, run_args, project_names,
                                       introspector_endpoint,
                                       args.run_logicfuzz_args)

  ret_val = _run_logicfuzz_command(logicfuzz_cmd, args.redirect_outs,
                                   local_results_dir, environ)

  logging.info("Shutting down introspector")
  try:
    subprocess.run(["curl", "--silent", "http://localhost:8080/api/shutdown"],
                   check=False,
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
  except Exception:
    pass

  # Exit with the return value of `./run_logicfuzz`.
  return ret_val

def run_standard(cmd=None):
  """The main function."""
  args = _parse_args(cmd)
  run_args = run_logicfuzz.parse_args(args.run_logicfuzz_args)

  python_path = _resolve_python_path()
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

  # Prepare the command to run experiments
  run_cmd = [python_path, "run_logicfuzz.py"] + args.run_logicfuzz_args

  ret_val = _run_logicfuzz_command(run_cmd, args.redirect_outs,
                                   local_results_dir)

  if args.local_introspector:
    logging.info("Shutting down introspector")
    try:
      subprocess.run(["curl", "--silent", "http://localhost:8080/api/shutdown"],
                     check=False,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    except Exception:
      pass

  # Exit with the return value of `./run_logicfuzz`.
  return ret_val

if __name__ == "__main__":
  sys.exit(main())
# /venv/bin/python3 run_logicfuzz.py -l gpt-5 -y conti-benchmark/cjson.yaml
