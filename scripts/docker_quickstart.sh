#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

LOGICFUZZ_IMAGE="${LOGICFUZZ_IMAGE:-logicfuzz}"
FI_IMAGE="${FI_IMAGE:-logicfuzz-introspector}"
MODEL="${LOGICFUZZ_MODEL:-qwen3-coder-plus}"
BENCHMARK_YAML="${BENCHMARK_YAML:-conti-benchmark/cjson.yaml}"
NUM_SAMPLES="${NUM_SAMPLES:-2}"
RUN_TIMEOUT="${RUN_TIMEOUT:-60}"
WORK_DIR="${WORK_DIR:-results/$(date +%Y%m%d-%H%M%S)}"
INTROSPECTOR_ENDPOINT="${INTROSPECTOR_ENDPOINT:-http://127.0.0.1:8080/api}"

echo "============================================"
echo " LogicFuzz Docker Quickstart"
echo " Repo root           : ${REPO_ROOT}"
echo " Runner image        : ${LOGICFUZZ_IMAGE}"
echo " Introspector image  : ${FI_IMAGE}"
echo " Model               : ${MODEL}"
echo " Benchmark YAML      : ${BENCHMARK_YAML}"
echo " Work dir            : ${WORK_DIR}"
echo " Introspector API    : ${INTROSPECTOR_ENDPOINT}"
echo "============================================"

if [ ! -f "${REPO_ROOT}/logicfuzz.env" ]; then
  echo "ERROR: logicfuzz.env not found in ${REPO_ROOT}."
  echo "       Please create it and populate your LLM API keys first."
  exit 1
fi

mkdir -p "${REPO_ROOT}/${WORK_DIR}"

echo "[1/3] Building runner image (${LOGICFUZZ_IMAGE})..."
docker build -t "${LOGICFUZZ_IMAGE}" -f "${REPO_ROOT}/Dockerfile" "${REPO_ROOT}"

echo "[2/3] Building Fuzz Introspector image (${FI_IMAGE})..."
docker build -t "${FI_IMAGE}" -f "${REPO_ROOT}/Dockerfile.fuzz-introspector" "${REPO_ROOT}"

echo "[3/3] Starting Fuzz Introspector container..."
docker rm -f logicfuzz-introspector-running >/dev/null 2>&1 || true
docker run -d --rm \
  --name logicfuzz-introspector-running \
  -p 8080:8080 \
  -v "${REPO_ROOT}/conti-benchmark:/opt/logicfuzz/conti-benchmark" \
  "${FI_IMAGE}" \
    --source benchmark \
    --benchmark-set comparison

trap 'docker rm -f logicfuzz-introspector-running >/dev/null 2>&1 || true' EXIT

echo "Waiting for Fuzz Introspector to become ready..."
for i in $(seq 1 30); do
  if curl -sf "${INTROSPECTOR_ENDPOINT}/healthz" >/dev/null 2>&1; then
    echo "Fuzz Introspector is up at ${INTROSPECTOR_ENDPOINT}"
    break
  fi
  echo "  Attempt ${i}/30: FI not ready yet, sleeping 5s..."
  sleep 5
done

if ! curl -sf "${INTROSPECTOR_ENDPOINT}/healthz" >/dev/null 2>&1; then
  echo "ERROR: Fuzz Introspector did not become ready in time."
  exit 1
fi

echo "Launching LogicFuzz runner container..."
docker run --rm \
  --privileged \
  --network host \
  --env-file "${REPO_ROOT}/logicfuzz.env" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "${REPO_ROOT}":/experiment \
  -w /experiment \
  "${LOGICFUZZ_IMAGE}" \
  python3 report/docker_run.py \
    --redirect-outs true \
    --model "${MODEL}" \
    -y "${BENCHMARK_YAML}" \
    --work-dir "${WORK_DIR}" \
    --num-samples "${NUM_SAMPLES}" \
    --run-timeout "${RUN_TIMEOUT}" \
    --introspector-endpoint "${INTROSPECTOR_ENDPOINT}" \
    --context

echo "LogicFuzz run finished."
echo "Results are under: ${WORK_DIR}"


