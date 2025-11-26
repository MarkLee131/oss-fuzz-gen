# Docker Environment Quickstart

This guide shows how to run LogicFuzz entirely inside Docker. Two images are provided:

1. `Dockerfile` &rarr; LogicFuzz experiment runner (`report/docker_run.py` wrapper).
2. `Dockerfile.fuzz-introspector` &rarr; stand‑alone Fuzz Introspector service.

## 1. Prerequisites
- Docker Engine/ Docker Desktop (24+ recommended).  
  - Linux: https://docs.docker.com/engine/install/
  - macOS / Windows: install Docker Desktop and keep it running.
- A cloned LogicFuzz repository.
- Export at least one LLM API key (OpenAI, Qwen/DashScope, Vertex AI, etc.).

## 2. Build the runner image
```bash
docker build -t logicfuzz -f Dockerfile .
```
The image ships with a virtualenv in `/venv` and copies the entire tree under `/experiment`. Pass `INSTALL_HOST_CLI=false` when you do not need the bundled Docker/gcloud tooling.

If you prefer a single command end‑to‑end setup, you can use the helper script:

```bash
bash scripts/docker_quickstart.sh
```

This script:
- Builds both `logicfuzz` (runner) and `logicfuzz-introspector` images.
- Starts a Fuzz Introspector container on port 8080.
- Runs one LogicFuzz experiment against `conti-benchmark/cjson.yaml` using the model specified via `LOGICFUZZ_MODEL` (default: `qwen3-coder-plus`).

## 3. Run experiments inside the container
`report/docker_run.py` is a thin wrapper around `run_logicfuzz.py`. It expects an already running Fuzz Introspector service (typically started from `Dockerfile.fuzz-introspector`) and executes the workflow. Reports remain as raw artifacts under `results/` and can be visualized later with `python -m report.web`.

```bash
# 1) Configure your LLM API keys following the example config file

cp logicfuzz.env.example logicfuzz.env

# Then edit logicfuzz.env and fill in DASHSCOPE_API_KEY / OPENAI_API_KEY, etc.


# 2) Prepare a results directory for this run
WORK_DIR="results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$WORK_DIR"

# 3) Start Fuzz Introspector in a separate container (see section 5), e.g.
#    (this will build a DB from the entire `conti-benchmark/` tree)
# docker run --rm -p 8080:8080 \
#   -v "$PWD"/conti-benchmark:/opt/logicfuzz/conti-benchmark \
#   logicfuzz-introspector \
#     --source benchmark

# 4) Launch LogicFuzz inside the runner container, passing env from logicfuzz.env
#    Most options are preset in scripts/docker_run_experiment.sh; override via
#    LOGICFUZZ_MODEL, BENCHMARK_YAML, WORK_DIR, etc. if needed.
docker run --rm \
  --privileged \
  --network host \
  --env-file logicfuzz.env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/experiment \
  -w /experiment \
  logicfuzz \
  bash scripts/docker_run_experiment.sh
```
  
> `--privileged` is needed because LogicFuzz spawns nested Docker builds

Key facts:
- The repo must be mounted at `/experiment`; results are written to `/experiment/results/*` so they persist on the host.
- If you omit `-y/--benchmark-yaml`, `-b/--benchmarks-directory`, and `-g/--generate-benchmarks`, the wrapper auto-selects `conti-benchmark` by injecting `-b conti-benchmark` before invoking `run_logicfuzz.py`, and `run_logicfuzz.py` will recursively load all YAMLs under that directory.
- Always point `--introspector-endpoint` (`-e`) to the external FI service started from `Dockerfile.fuzz-introspector`.
- Add `--redirect-outs true` to tee stdout/stderr into `results/logs-from-run.txt`.

## 4. Using the “data-dir” workflow (non OSS-Fuzz projects)
When `/experiment/data-dir` exists (or `/experiment/data-dir.zip` is mounted), the container switches to `run_on_data_from_scratch()`:

1. Mount your prepared directory (or drop a zipped archive) that contains:
   - `oss-fuzz2/` &rarr; custom OSS-Fuzz clone with your projects.
   - `fuzz_introspector_db/` &rarr; prebuilt FI database.
2. Start a dedicated FI container using the same `data-dir` (see examples in section 5), so that the FI service exposes `http://127.0.0.1:8080/api`.
3. The wrapper calls `run_logicfuzz.py -g ...` against that endpoint with the heuristics configured in `docker_run.py` (`far-reach-low-coverage, low-cov-with-fuzz-keyword, easy-params-far-reach`).
4. Reports are labeled `<date>-<benchmark_label>` so you can host them from the generated HTML output if you choose to run `python -m report.web`.

Use this mode when onboarding internal/private projects that are not part of upstream OSS-Fuzz but already have collected coverage + build artifacts.

## 5. Build the stand-alone Fuzz Introspector image
```bash
docker build -t logicfuzz-introspector -f Dockerfile.fuzz-introspector .
```
The entrypoint is `bash /opt/logicfuzz/report/launch_introspector.sh`, so all CLI flags supported by that script are available.

### Example: start FI from the shipped benchmarks
```bash
docker run --rm -p 8080:8080 \
  -v "$PWD"/conti-benchmark:/opt/logicfuzz/conti-benchmark \
  logicfuzz-introspector \
    --source benchmark \
    --benchmark-set comparison
```

### Example: reuse an existing `data-dir`
```bash
docker run --rm -p 8080:8080 \
  -v /path/to/data-dir:/opt/logicfuzz/data-dir \
  logicfuzz-introspector \
    --source data-dir \
    --data-dir /opt/logicfuzz/data-dir
```

## 6. Verifying outputs
- Experiment artifacts: `results/output-*/` (on host because of the bind mount).
- HTML reports: run `python -m report.web -r results -b <benchmark_set> -m <model> -o report/html-report/<label>/` when you need them.
- FI service health: curl `http://127.0.0.1:8080/api/healthz`.

If the runner container exits with a non-zero status, inspect `results/logs-from-run.txt` (when `--redirect-outs true`) or the host terminal output. Since Docker uses your host Docker daemon through `/var/run/docker.sock`, make sure Docker Desktop/Engine is running before launching LogicFuzz.