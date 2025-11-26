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
  --help
```
The image’s `ENTRYPOINT` already runs `python3 report/docker_run.py`, so you only pass flags. Use the `--help` output to confirm the flag set mirrors `run_logicfuzz.py`. Start a real experiment by swapping in your desired arguments—for example:
```bash
docker run --rm -it \
  -v "$PWD":/experiment \
  -w /experiment \
  logicfuzz \
    --model qwen3-coder-plus \
    -y conti-benchmark/cjson.yaml \
    --work-dir results/$(date +%Y%m%d-%H%M%S) \
    --num-samples 1 \
    --context
```
所有实验参数现在都直接传递给 `run_logicfuzz.py`；不需要再使用单独的 `--benchmark-set` 包装参数。想运行整个目录就传 `--benchmarks-directory conti-benchmark/cjson`，想只跑一个 YAML 就用 `-y conti-benchmark/cjson.yaml`。如果完全不指定，容器会回退到 `conti-benchmark/comparison`。

容器仍会默认拉起本地 Fuzz Introspector (`http://127.0.0.1:8080`)；若你已经有现成实例，可加 `--local-introspector false` 禁用。

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

