# Docker Environment Quickstart

Follow these steps exactly and you will have both LogicFuzz containers ready. No prior Docker knowledge required.

## 1. Install the prerequisites
- Install Docker Engine (version 24+ recommended).  
  - Linux: follow https://docs.docker.com/engine/install/#server
  - macOS/Windows: install Docker Desktop and ensure it is running.
- Clone this repository and `cd` into it.

## 2. Build the experiment runner image
```bash
docker build -t logicfuzz:latest -f Dockerfile .
```
This image runs the main LogicFuzz experiment workflow via `report/docker_run.py`.

## 3. Launch the experiment runner
The runner image expects the repo root mounted at `/experiment`, which `report/docker_run.py` uses as its working tree.
```bash
docker run --rm -it \
  -v "$PWD":/experiment \
  -w /experiment \
  logicfuzz \
  python3 report/docker_run.py --help
```
Use the `--help` output to confirm the flag set mirrors `run_logicfuzz.py`. Start a real experiment by swapping in your desired arguments—for example:
```bash
docker run --rm -it \
  -v "$PWD":/experiment \
  -w /experiment \
  logicfuzz \
  python3 report/docker_run.py \
    --model qwen3-coder-plus \
    --benchmark-set conti-benchmark/cjson.yaml \
    --work-dir results/$(date +%Y%m%d-%H%M%S) \
    --num-samples 1
```
Pass any extra `run_logicfuzz.py` parameters after `--additional-args -- ...`.

## 4. Build the Fuzz Introspector image
```bash
docker build -t logicfuzz-introspector -f Dockerfile.fuzz-introspector .
```
This image analyzes experiment outputs with Fuzz Introspector.

## 5. Launch the Fuzz Introspector
```bash
docker run --rm -it \
  -v "$PWD":/opt/logicfuzz \
  -w /opt/logicfuzz \
  logicfuzz-introspector
```
The container automatically calls `report/launch_introspector.sh`. Mount the same repo so reports and results are shared.

## 6. Verify results
- Experiment logs appear under `results/` inside the repo (and under `/experiment/results` in the runner container). Each run uses the label shown at startup.
- Introspector exports live under `report/` using the paths configured in `report/upload_report.sh`. Share the same host directory so both containers see the outputs.

Done! If a command fails, read the message, fix the issue (usually a missing dependency or wrong path), and rerun the same step.

