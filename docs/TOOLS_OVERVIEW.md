# LogicFuzz Tools Overview

This document explains the different tools in LogicFuzz, their relationships, and when to use each one.

---

## 🎯 Quick Decision Guide

**I have an existing OSS-Fuzz project and want to generate fuzz targets**
→ Use `run_logicfuzz.py` with benchmark YAML files

**I want to onboard a new project to OSS-Fuzz from GitHub**
→ Use `experimental.end_to_end.cli` module (run with `python3 -m experimental.end_to_end.cli`)

**I'm developing locally and need a quick harness for testing**
→ Use `experimental.from_scratch.generate` module

**My OSS-Fuzz build is failing and needs fixing**
→ Use `python3 -m experimental.end_to_end.cli fix-build`

---

## 🏗️ Architecture: Three Layers

```
┌─────────────────────────────────────────────────────────┐
│                   User-Facing Tools                      │
│  (What you interact with)                               │
├─────────────────────────────────────────────────────────┤
│  • run_logicfuzz.py / run_single_fuzz.py               │
│  • experimental.end_to_end.cli (end-to-end)           │
│  • experimental.from_scratch.generate                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Core Libraries                         │
│  (Imported by tools)                                    │
├─────────────────────────────────────────────────────────┤
│  • agent_graph/ - Multi-agent workflow                 │
│  • experiment/ - Build & evaluation                     │
│  • data_prep/ - FuzzIntrospector client                │
│  • experimental/build_generator/ - Build generation    │
│  • experimental/build_fixer/ - Build fixing            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Support Tools                          │
│  (Auxiliary utilities)                                  │
├─────────────────────────────────────────────────────────┤
│  • report/ - FuzzIntrospector server & reports         │
│  • llm_toolkit/ - LLM API abstraction                  │
│  • tool/ - Agent tools                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 📚 User-Facing Tools

### 1. Main Workflow: `run_logicfuzz.py` & `run_single_fuzz.py`

**Purpose:** Generate fuzz targets for existing OSS-Fuzz projects

**Use when:** You have benchmark YAML files (from `conti-benchmark/` or manually created)

**Features:**
- Multi-agent LLM-based fuzz target generation
- Coverage-driven optimization
- Crash detection and analysis
- Batch processing support

**Usage:**
```bash
# Batch mode: Process all functions in benchmark
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api

# Single function mode
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/libxml2.yaml \
  -f xmlParseDocument \
  --model gpt-5

# Extended optimization
python run_logicfuzz.py --agent \
  -y benchmark.yaml \
  --model gpt-5 \
  --max-round 15 \
  --run-timeout 600
```

**Key Parameters:**
| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `--model` | LLM model | - | `gpt-5`, `gemini-2.0-flash-exp` |
| `-e, --fuzz-introspector-endpoint` | FI API URL | None | `http://0.0.0.0:8080/api` |
| `--num-samples` | Trials per function | 5 | 5-10 |
| `--max-round` | Max optimization iterations | 5 | 5-15 |
| `--run-timeout` | Fuzzer runtime (seconds) | 60 | 60-600 |

**Output:**
```
results/
├── output-{project}-{function}/
│   ├── fuzz_targets/           # Generated harnesses
│   ├── code-coverage-reports/  # Coverage data
│   ├── status/                 # Build/run results
│   └── benchmark.yaml          # Used configuration
└── report.json                 # Aggregate results
```

**Related Files:**
- `run_logicfuzz.py` - Batch runner (calls `run_single_fuzz.py`)
- `run_single_fuzz.py` - Single benchmark runner
- `agent_graph/` - Multi-agent workflow implementation

---

### 2. End-to-End Workflow: `experimental.end_to_end.cli`

**Purpose:** Generate complete OSS-Fuzz projects from GitHub repositories

**Use when:** Onboarding new projects to OSS-Fuzz from scratch

**Features:**
- Automated build script generation
- Build error fixing with LLM
- Fuzz harness generation
- Full project integration (Dockerfile + build.sh + fuzzers)

**How to run:**
```bash
# Run as Python module (no installation needed)
python3 -m experimental.end_to_end.cli [command]
```

**Commands:**

#### 2.1 `generate-builds` - Generate Build Scripts Only
```bash
# Generate build scripts for repositories
python3 -m experimental.end_to_end.cli generate-builds \
  -m gpt-5 \
  -i input.txt \
  --oss-fuzz /path/to/oss-fuzz \
  -o generated-builds
```

**Input file format (`input.txt`):**
```
https://github.com/user/repo1
https://github.com/user/repo2
https://github.com/user/repo3
```

**Output:**
```
generated-builds/
└── oss-fuzz-projects/
    ├── repo1-agent/
    │   ├── Dockerfile
    │   ├── build.sh
    │   └── project.yaml
    └── repo2-agent/
        └── ...
```

#### 2.2 `generate-fuzz-introspector-database` - Prepare FI Database
```bash
# Create FuzzIntrospector database from generated builds
python3 -m experimental.end_to_end.cli generate-fuzz-introspector-database \
  --generated-builds generated-builds \
  --workdir /path/to/workdir \
  --parallel-build-jobs 5
```

#### 2.3 `generate-harnesses` - Generate Fuzz Harnesses
```bash
# Generate fuzz harnesses for prepared projects
python3 -m experimental.end_to_end.cli generate-harnesses \
  -m gpt-5 \
  -w /path/to/workdir \
  --project myproject \
  --function-name target_function
```

#### 2.4 `generate-full` - Complete End-to-End Pipeline
```bash
# Single repository
python3 -m experimental.end_to_end.cli generate-full \
  -m gpt-5 \
  -i "https://github.com/kgabis/parson"

# Multiple repositories
echo "https://github.com/zserge/jsmn" > repos.txt
echo "https://github.com/rafagafe/tiny-json" >> repos.txt
python3 -m experimental.end_to_end.cli generate-full -m gpt-5 -i repos.txt

# With custom settings
python3 -m experimental.end_to_end.cli generate-full \
  -m gpt-5 \
  -i repos.txt \
  --build-jobs 4 \
  --max-round 10 \
  --generate-benchmarks-max 5
```

**Output:**
```
final-oss-fuzz-projects/
├── parson-agent/
│   ├── build.sh
│   ├── Dockerfile
│   ├── empty-fuzzer.0.c
│   ├── empty-fuzzer.1.c
│   └── project.yaml
└── jsmn-agent/
    └── ...
```

#### 2.5 `fix-build` - Automated Build Fixing
```bash
# Fix failing OSS-Fuzz build scripts
python3 -m experimental.end_to_end.cli fix-build \
  --project myproject \
  --model gpt-5 \
  --max-round 20
```

**Related Files:**
- `experimental/end_to_end/cli.py` - CLI implementation
- `experimental/build_generator/` - Build generation library
- `experimental/build_fixer/` - Build fixing library

---

### 3. Quick Prototyping: `experimental.from_scratch.generate`

**Purpose:** Rapid harness generation for local codebases (no OSS-Fuzz project needed)

**Use when:** 
- Testing a function locally during development
- Don't need full OSS-Fuzz integration
- Want minimal setup

**Features:**
- Simple function-to-harness generation
- No Docker/OSS-Fuzz infrastructure required
- Fast iteration for developers

**Usage:**
```bash
# Clone target repository
git clone https://github.com/dvhar/dateparse ../dateparse

# Generate harness for specific function
python3 -m experimental.from_scratch.generate \
  -l c++ \
  -m gpt-5 \
  -f dateparse \
  -t ../dateparse/ \
  -o out_cpp

# View generated harness
cat out_cpp/01.rawoutput
```

**Output:**
```c
#include <stdio.h>
#include <string.h>

typedef struct{int year;int month; int day;} date_t;

int dateparse(const char* datestr, date_t* t, int *offset, int stringlen);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    date_t t;
    int offset = 0;
    
    char* datestr = (char*)malloc(size + 1);
    if (!datestr) return 0;
    memcpy(datestr, data, size);
    datestr[size] = '\0';
    
    dateparse(datestr, &t, &offset, size);
    
    free(datestr);
    return 0;
}
```

**Comparison with other tools:**

| Feature | from_scratch | run_logicfuzz | end_to_end.cli |
|---------|-------------|---------------|-----------------|
| Requires OSS-Fuzz | ❌ No | ✅ Yes | ✅ Yes (creates) |
| Requires FuzzIntrospector | ❌ No | ⚠️ Optional | ⚠️ Optional |
| Multi-agent workflow | ❌ No | ✅ Yes | ✅ Yes |
| Coverage optimization | ❌ No | ✅ Yes | ✅ Yes |
| Build script generation | ❌ No | ❌ No | ✅ Yes |
| Speed | ⚡ Fast | 🐌 Slow | 🐢 Very Slow |
| Best for | Local dev | Evaluation | Production |

**Related Files:**
- `experimental/from_scratch/generate.py` - Main module
- `experimental/from_scratch/README.md` - Detailed guide

---

## 🔧 Core Libraries

These are not meant to be used directly - they are imported by the user-facing tools.

### 1. `agent_graph/` - Multi-Agent Workflow

**Purpose:** LangGraph-based supervisor-agent system for fuzz target generation

**Components:**
- `workflow.py` - LangGraph StateGraph + FuzzingWorkflow
- `state.py` - State schema + Session Memory API
- `nodes/` - LangGraph node wrappers (Supervisor, Analyzer, Prototyper, etc.)
- `agents/` - Core LLM agent logic

**Used by:** `run_logicfuzz.py`, `run_single_fuzz.py`, `experimental.end_to_end.cli`

---

### 2. `experiment/` - Build & Evaluation Infrastructure

**Purpose:** OSS-Fuzz Docker integration, compilation, coverage collection

**Components:**
- `builder_runner.py` - Docker build execution
- `evaluator.py` - Coverage + crash detection
- `textcov.py` - LLVM coverage parsing
- `oss_fuzz_checkout.py` - OSS-Fuzz management

**Used by:** All tools that need to build/run fuzz targets

---

### 3. `data_prep/` - FuzzIntrospector Integration

**Purpose:** API client for Fuzz Introspector (function analysis, call graphs, etc.)

**Components:**
- `introspector.py` - Complete FI API client (1500+ lines)
- `project_context/` - Context extraction utilities

**Used by:** `agent_graph/`, `tool/`, all workflows needing project context

---

### 4. `experimental/build_generator/` - Build Script Generation

**Purpose:** Automated OSS-Fuzz build script creation

**Used by:** `python3 -m experimental.end_to_end.cli generate-builds`

**Note:** This is a library. For CLI usage, use `experimental.end_to_end.cli` instead of calling this directly.

---

### 5. `experimental/build_fixer/` - Build Error Fixing

**Purpose:** LLM-powered build error resolution

**Used by:** `python3 -m experimental.end_to_end.cli fix-build`

**Note:** This is a library. For CLI usage, use `experimental.end_to_end.cli` instead of calling this directly.

---

## 🛠️ Support Tools

### 1. `report/` - FuzzIntrospector Server & Reporting

**Files:**
- `launch_introspector.sh` - Unified FI server launcher
- `compare_results.py` - Result comparison
- `web.py` - Web report generation

**Usage:**
```bash
# Start FuzzIntrospector server (benchmark mode - default)
./report/launch_introspector.sh

# Start with data-dir source (for end-to-end workflow)
./report/launch_introspector.sh --source data-dir --data-dir /path/to/data-dir

# Custom benchmark set
./report/launch_introspector.sh --benchmark-set my-benchmarks

# Show help
./report/launch_introspector.sh --help
```

---

### 2. `llm_toolkit/` - LLM API Abstraction

**Purpose:** Unified interface for OpenAI, Vertex AI (Gemini), etc.

**File:** `models.py`

**Used by:** All agents in `agent_graph/`

---

### 3. `tool/` - Agent Tools

**Purpose:** Tools that LLM agents can use (FuzzIntrospector queries, file operations)

**Files:**
- `fuzz_introspector_tool.py` - FI API wrapper for agents
- `base_tool.py` - Base tool class

**Used by:** `agent_graph/agents/`

---

## 📊 Use Case Matrix

| Scenario | Tool | Prerequisites | Output |
|----------|------|---------------|--------|
| **Generate targets for existing OSS-Fuzz project** | `run_logicfuzz.py` | • Benchmark YAML<br>• OSS-Fuzz project exists<br>• (Optional) FI server | Fuzz targets + coverage reports |
| **Onboard new GitHub repo to OSS-Fuzz** | `experimental.end_to_end.cli generate-full` | • GitHub repo URL<br>• LLM API key | Complete OSS-Fuzz project |
| **Generate build scripts only** | `experimental.end_to_end.cli generate-builds` | • GitHub repo URL<br>• OSS-Fuzz clone | Dockerfile + build.sh + project.yaml |
| **Fix failing OSS-Fuzz build** | `experimental.end_to_end.cli fix-build` | • OSS-Fuzz project<br>• Build error | Fixed build.sh |
| **Quick local harness for testing** | `experimental.from_scratch.generate` | • Local codebase<br>• Function name | Single fuzz harness (no OSS-Fuzz) |
| **Evaluate multiple models** | `run_logicfuzz.py` (multiple runs) | • Benchmark YAML<br>• Multiple LLM API keys | Comparative results |
| **Start FuzzIntrospector server** | `report/launch_introspector.sh` | • Benchmarks or data-dir | Running FI API server |

---

## 🔄 Common Workflows

### Workflow 1: Standard Fuzzing Campaign

```bash
# Step 1: Start FuzzIntrospector (optional but recommended)
./report/launch_introspector.sh

# Step 2: Run LogicFuzz
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/libxml2.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --num-samples 10 \
  --max-round 10

# Step 3: Analyze results
ls results/output-libxml2-*/
cat results/report.json
```

### Workflow 2: New Project Onboarding

```bash
# Step 1: Generate complete OSS-Fuzz project
echo "https://github.com/user/mylib" > repos.txt
python3 -m experimental.end_to_end.cli generate-full -m gpt-5 -i repos.txt

# Step 2: Review generated project
ls final-oss-fuzz-projects/mylib-agent/

# Step 3: Test build
cd final-oss-fuzz-projects/mylib-agent/
docker build -t gcr.io/oss-fuzz/mylib .

# Step 4: Run fuzzer
docker run --rm gcr.io/oss-fuzz/mylib
```

### Workflow 3: Local Development

```bash
# Quick harness generation for local testing
git clone https://github.com/user/mylib ../mylib

python3 -m experimental.from_scratch.generate \
  -l c++ \
  -m gpt-5 \
  -f my_function \
  -t ../mylib/ \
  -o ./harness_output

# Compile and test locally (without Docker)
clang++ -fsanitize=fuzzer,address harness_output/01.rawoutput -o fuzzer
./fuzzer
```

---

## 🎓 Learning Path

**New to LogicFuzz?** Follow this path:

1. **Start Simple** → Use `experimental.from_scratch.generate` for quick local testing
2. **Understand Benchmarks** → Read `data_prep/README.md` to learn about benchmark YAMLs
3. **Run Standard Workflow** → Use `run_logicfuzz.py` with existing benchmarks
4. **Advanced: End-to-End** → Use `experimental.end_to_end.cli` for complete project generation
5. **Deep Dive** → Read `agent_graph/README.md` for multi-agent architecture

---

## 📖 Further Reading

- **Architecture:** [agent_graph/README.md](../agent_graph/README.md) - Multi-agent workflow details
- **Benchmarks:** [data_prep/README.md](../data_prep/README.md) - Benchmark YAML generation
- **New Projects:** [NEW_PROJECT_SETUP.md](NEW_PROJECT_SETUP.md) - Complete setup guide
- **Fuzzing Best Practices:** [FUZZER_COOKBOOK.md](FUZZER_COOKBOOK.md)
- **Quick Reference:** [FUZZING_CHEATSHEET.md](FUZZING_CHEATSHEET.md)

---

## ❓ FAQ

### Q: What's the difference between `run_logicfuzz.py` and `experimental.end_to_end.cli`?

**A:** 
- `run_logicfuzz.py` - For **existing** OSS-Fuzz projects (generates fuzz targets only)
- `experimental.end_to_end.cli` - For **new** projects (generates entire OSS-Fuzz integration)

### Q: Do I need FuzzIntrospector running?

**A:** No, but highly recommended. Without FI:
- Lower quality context (no call graphs, usage examples)
- May result in lower compilation success rate
- Agents have less information about API usage

### Q: Can I use LogicFuzz without Docker?

**A:** Yes, use `experimental.from_scratch.generate` for local harness generation. However:
- No OSS-Fuzz integration
- No coverage reports
- No crash detection pipeline
- Manual compilation required

### Q: Which tool should I use for batch processing?

**A:** `run_logicfuzz.py` with benchmark YAMLs. It handles:
- Parallel execution (`LLM_NUM_EXP` environment variable)
- Aggregate reporting
- Coverage comparison

### Q: How do I debug build failures?

**A:** 
1. Check `results/output-{project}-{function}/status/{trial}/result.json`
2. Look for compiler errors in build logs
3. Use `python3 -m experimental.end_to_end.cli fix-build` for automated fixing
4. Review `agent_graph/nodes/execution_node.py` for build logic

---

## 🤝 Contributing

When adding new tools:
1. Place user-facing tools at top level
2. Place libraries under appropriate directories
3. Update this document
4. Add examples to relevant README files
5. Ensure tool relationships are clear

---

**Last Updated:** 2025-01-20  
**Maintainer:** LogicFuzz Team

