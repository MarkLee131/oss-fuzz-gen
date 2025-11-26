# Running LogicFuzz

This guide covers how to run LogicFuzz, from basic usage to advanced configurations and deployment.

## 🚀 Quick Start

### Prerequisites

1.  **LLM API Keys** (set environment variables):
    ```bash
    # OpenAI (GPT-4, GPT-5)
    export OPENAI_API_KEY="sk-..."
    
    # Vertex AI (Gemini models)
    export VERTEX_AI_PROJECT_ID="your-project"
    
    # DeepSeek
    export DEEPSEEK_API_KEY="sk-..."
    
    # Qwen (Alibaba Cloud DashScope)
    export DASHSCOPE_API_KEY="sk-..."
    # Optional: Override API endpoint (defaults to Singapore region)
    export QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    ```
    
    **Getting API Keys:**
    *   **OpenAI**: [platform.openai.com](https://platform.openai.com)
    *   **Vertex AI**: [Google Cloud Console](https://console.cloud.google.com)
    *   **DeepSeek**: [platform.deepseek.com](https://platform.deepseek.com)
    *   **Qwen**: [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/get-api-key)

2.  **Fuzz Introspector Server** (optional, recommended for better context):
    ```bash
    # Start FI in benchmark mode (default set = comparison)
    bash report/launch_introspector.sh --source benchmark --benchmark-set comparison
    ```
    The script also supports `--source data-dir --data-dir <path>` when you already have a populated FI database.

### Basic Usage

Run LogicFuzz on a specific function in a benchmark project:

```bash
# Target a specific function
python run_logicfuzz.py \
  -y conti-benchmark/conti-cmp/libxml2.yaml \
  -f xmlParseDocument \
  --model gpt-5
```

## 🐳 Docker Deployment

LogicFuzz provides Docker support for easy deployment and reproducibility.

### Build Docker Image

```bash
docker build -t logicfuzz:latest .
```

### Run Docker Container

```bash
docker run --rm \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/experiment \
  -w /experiment \
  -e OPENAI_API_KEY="sk-..." \
  logicfuzz:latest \
  python3 report/docker_run.py \
    --model gpt-5 \
    --benchmarks-directory conti-benchmark/comparison \
    --run-timeout 300 \
    --local-introspector true
```

**Notes:**
*   `--privileged` plus the Docker socket mount let the container call `infra/helper.py` inside OSS-Fuzz images.
*   Mount the entire repo (not just `results/`) so `report/docker_run.py` can access benchmarks, scripts, and write results alongside the sources.
*   Pass `--local-introspector false` and `-e http://host.docker.internal:8080/api` when you already run FI on the host.

### Split Deployment (LogicFuzz + Fuzz Introspector)

Run Fuzz Introspector in its own container so LogicFuzz can be upgraded or restarted independently.

1. Build the dedicated image:
    ```bash
    docker build -f Dockerfile.fuzz-introspector -t logicfuzz-fi .
    ```
2. Launch the FI server (benchmark mode):
    ```bash
    docker run --rm -p 8080:8080 \
      -v $(pwd)/conti-benchmark:/opt/logicfuzz/conti-benchmark \
      logicfuzz-fi --source benchmark --benchmark-set comparison
    ```
   or reuse an already-populated data directory:
    ```bash
    docker run --rm -p 8080:8080 \
      -v /path/to/data-dir:/opt/logicfuzz/data-dir \
      logicfuzz-fi --source data-dir --data-dir data-dir
    ```
3. Point LogicFuzz to the running server:
    ```bash
    python run_logicfuzz.py ... \
      -e http://localhost:8080/api
    ```

#### docker compose example

```yaml
version: "3.9"
services:
  logicfuzz:
    build: .
    privileged: true
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command:
      [
        "python3", "report/docker_run.py",
        "--local-introspector", "false",
        "-y", "conti-benchmark/conti-cmp/cjson.yaml",
        "--introspector-endpoint", "http://fuzz-introspector:8080/api",
        "--model", "gpt-5"
      ]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/experiment
  fuzz-introspector:
    build:
      context: .
      dockerfile: Dockerfile.fuzz-introspector
    ports:
      - "8080:8080"
    volumes:
      - ./conti-benchmark:/opt/logicfuzz/conti-benchmark
      - ./data-dir:/opt/logicfuzz/data-dir
```

The compose file above is only an example—adjust benchmark/data directories and model arguments to match your workflow. Rebuilding the FI database (by updating `data-dir` or the benchmark set) only requires restarting the `fuzz-introspector` service.

## 🎓 Advanced Usage

### Batch Processing
Process all functions in a benchmark YAML:

```bash
python run_logicfuzz.py \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --num-samples 10
```

### Bug Hunting Mode
Focus on crash discovery with extended fuzzing time and multiple samples:

```bash
python run_logicfuzz.py \
  -y conti-benchmark/conti-cmp/libpng.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --run-timeout 1800 \
  --num-samples 10 \
  --temperature 0.6
```

### Local Development (No FI Server)
Works without Fuzz Introspector (reduced context quality):

```bash
python run_logicfuzz.py \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5 \
  --num-samples 3
```

## 🔧 Configuration

### Key Parameters

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `--model` | LLM model name | - | `gpt-5`, `gemini-2.0-flash-exp`, `qwen3` |
| `-e, --introspector-endpoint` | FI server URL | `http://127.0.0.1:8080/api` | `http://0.0.0.0:8080/api` |
| `--num-samples` | Trials per function | 5 | 5-10 |
| `--temperature` | LLM temperature | 0.4 | 0.3-0.5 |
| `--run-timeout` | Fuzzer runtime (seconds) | 60 | 60-300 |
| `-w, --work-dir` | Output directory | `./results` | - |

### Supported Models

#### OpenAI (GPT Series)
*   **Models**: `gpt-4`, `gpt-4o`, `gpt-4-turbo`, `gpt-5`, `gpt-5.1`
*   **API**: OpenAI official API
*   **Endpoint**: `https://api.openai.com/v1`

#### Qwen (OpenAI Compatible)
*   **Models**: `qwen-turbo` (8K), `qwen-plus` (131K), `qwen-max` (30K), `qwen3` (32K)
*   **API**: Alibaba Cloud DashScope with OpenAI-compatible interface
*   **Endpoints**:
    *   Singapore (default): `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
    *   Beijing: `https://dashscope.aliyuncs.com/compatible-mode/v1`
*   **Note**: Uses OpenAI SDK internally for seamless integration

#### Vertex AI (Gemini Series)
*   **Models**: `gemini-2.0-flash-exp`, `gemini-2-5-pro`, `gemini-2-5-flash`, etc.
*   **API**: Google Cloud Vertex AI
*   **Endpoint**: Regional (configurable via `VERTEX_AI_LOCATIONS`)

#### DeepSeek
*   **Models**: `deepseek-chat` (128K), `deepseek-reasoner` (128K)
*   **API**: DeepSeek official API
*   **Endpoint**: `https://api.deepseek.com/v1`

## 🌐 Using Qwen with OpenAI-Compatible API

LogicFuzz integrates Qwen models through Alibaba Cloud's DashScope service using the **OpenAI-compatible interface**. This means:

1. **No Additional Dependencies**: Uses the same `openai` Python package as GPT models
2. **Seamless Integration**: Same API interface, just different endpoint and model names
3. **Full Feature Support**: Supports all LogicFuzz features (streaming, multi-turn, etc.)

### Quick Setup

```bash
# 1. Get your API key from Alibaba Cloud Model Studio
# Visit: https://www.alibabacloud.com/help/en/model-studio/get-api-key

# 2. Set the API key
export DASHSCOPE_API_KEY="sk-..."

# 3. (Optional) Choose region - defaults to Singapore
export QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"  # Singapore
# export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"      # Beijing

# 4. Run LogicFuzz
python run_logicfuzz.py \
  -y conti-benchmark/conti-cmp/libxml2.yaml \
  --model qwen3 \
  --num-samples 5
```

### API Endpoints

| Region | Base URL | Use Case |
|--------|----------|----------|
| **Singapore** (default) | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | International users, lower latency outside China |
| **Beijing** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | China mainland users |

### Model Selection Guide

| Model | Context | Speed | Quality | Best For |
|-------|---------|-------|---------|----------|
| `qwen-turbo` | 8K | ⚡⚡⚡ | ⭐⭐ | Quick iterations, cost-effective |
| `qwen-plus` | 131K | ⚡⚡ | ⭐⭐⭐ | Long context, complex projects |
| `qwen-max` | 30K | ⚡ | ⭐⭐⭐⭐ | Highest quality, challenging bugs |
| `qwen3` | 32K | ⚡⚡ | ⭐⭐⭐ | Balanced performance (recommended) |

### Example: Running with Different Qwen Models

```bash
# Fast iteration with Qwen Turbo
python run_logicfuzz.py -y benchmark.yaml --model qwen-turbo --num-samples 3

# Long context with Qwen Plus
python run_logicfuzz.py -y benchmark.yaml --model qwen-plus --num-samples 5

# Best quality with Qwen Max
python run_logicfuzz.py -y benchmark.yaml --model qwen-max --num-samples 5

# Recommended: Qwen3 (balanced)
python run_logicfuzz.py -y benchmark.yaml --model qwen3 --num-samples 5
```

### Verification

Test your Qwen configuration:

```bash
python test_qwen_openai_compat.py
```

This will verify:
- ✅ API key is properly set
- ✅ Base URL is configured correctly
- ✅ OpenAI-compatible client can be created
- ✅ All Qwen models are available

## 🐛 Troubleshooting

### Common Issues

**Compilation Fails After 3 Retries**
*   Check if library is available in OSS-Fuzz.
*   Verify target function signature is correct.
*   Review build errors in `./results/*/build_log.txt`.

**Target Function Not Called**
*   Verify function name in YAML matches actual code.
*   Check if function is static/internal (may not be accessible).

**No Crashes Found**
*   Increase `--run-timeout` (longer fuzzing time).
*   Increase `--num-samples` (more diverse targets).

