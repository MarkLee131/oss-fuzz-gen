# LogicFuzz

**Automated Fuzz Target Generation with Multi-Agent LLMs**

LogicFuzz uses AI agents to automatically generate, compile, and validate fuzz targets for C/C++ projects. It streamlines the process into two phases: **Compilation** (making it build) and **Optimization** (finding bugs).

---

## 🚀 Quick Start

### 1. Prerequisites
*   **Docker** (must be installed and running)
*   **LLM API Key** (choose one):
    *   OpenAI (GPT-4, GPT-5)
    *   Qwen via Alibaba Cloud DashScope (recommended for cost efficiency)

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Qwen (Singapore region)
export DASHSCOPE_API_KEY="sk-..."
export QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
```

> 📖 Get your Qwen API key: [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/get-api-key)

### 2. Run LogicFuzz
Generate a fuzzer for a sample benchmark:

```bash
# Using OpenAI GPT-5
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5

# Using Qwen Plus (cost-efficient alternative)
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model qwen-plus
```

---

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| **[Running LogicFuzz](docs/RUNNING.md)** | Detailed usage, configuration options, and troubleshooting. |
| **[New Project Setup](docs/NEW_PROJECT_SETUP.md)** | How to onboard new projects (OSS-Fuzz, private repos, custom builds). |
| **[Architecture](docs/ARCHITECTURE.md)** | Inner workings: Supervisor-Agent pattern, Session Memory, and workflows. |
| **[Agent Graph](agent_graph/README.md)** | Deep dive into the code implementation. |

---

## 📄 License
Apache 2.0 License - See [LICENSE](LICENSE) file for details.
