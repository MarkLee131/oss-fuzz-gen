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
# Optional: strip Docker/gcloud CLIs to shrink the image.
# docker build -t logicfuzz -f Dockerfile --build-arg INSTALL_HOST_CLI=false .
```
The image ships with a virtualenv in `/venv` and copies the entire tree under `/experiment`. Pass `INSTALL_HOST_CLI=false` when you do not need the bundled Docker/gcloud tooling.

## 3. Run experiments inside the container
`report/docker_run.py` is a thin wrapper around `run_logicfuzz.py`. It launches a local Fuzz Introspector (unless told otherwise) and executes the workflow. Reports remain as raw artifacts under `results/` and can be visualized later with `python -m report.web`.

```bash
docker run --rm -it \
  --privileged \  # needed because LogicFuzz spawns nested Docker builds
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/experiment \
  -w /experiment \
  logicfuzz \
  python3 report/docker_run.py \
    --model qwen3 \
    -y conti-benchmark/conti-cmp/cjson.yaml \
    --work-dir results/$(date +%Y%m%d-%H%M%S) \
    --num-samples 2 \
    --context
```

Key facts:
- The repo must be mounted at `/experiment`; results are written to `/experiment/results/*` so they persist on the host.
- If you omit `-y/--benchmark-yaml`, `-b/--benchmarks-directory`, and `-g/--generate-benchmarks`, the wrapper auto-selects `conti-benchmark` by injecting `-b conti-benchmark` before invoking `run_logicfuzz.py`, and `run_logicfuzz.py` will recursively load all YAMLs under that directory.
- Add `--local-introspector false` to re-use an existing FI endpoint (`-e/--introspector-endpoint`).
- Add `--redirect-outs true` to tee stdout/stderr into `results/logs-from-run.txt`.

## 4. Using the “data-dir” workflow (non OSS-Fuzz projects)
When `/experiment/data-dir` exists (or `/experiment/data-dir.zip` is mounted), the container switches to `run_on_data_from_scratch()`:

1. Mount your prepared directory (or drop a zipped archive) that contains:
   - `oss-fuzz2/` &rarr; custom OSS-Fuzz clone with your projects.
   - `fuzz_introspector_db/` &rarr; prebuilt FI database.
2. The wrapper starts `report/custom_oss_fuzz_fi_starter.sh`, launches FI at `http://127.0.0.1:8080/api`, and calls `run_logicfuzz.py -g ...` with the heuristics configured in the script (`far-reach-low-coverage, low-cov-with-fuzz-keyword, easy-params-far-reach`).
3. Reports are labeled `<date>-<benchmark_label>` so you can host them from the generated HTML output if you choose to run `python -m report.web`.

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