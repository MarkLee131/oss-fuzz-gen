# LogicFuzz

**Multi-Agent Automated Fuzz Target Generation using LLM Agents**

LogicFuzz is an intelligent fuzzing framework that leverages **multi-agent LLM collaboration** to automatically generate high-quality fuzz targets. It uses a **Supervisor-Agent pattern with streamlined two-phase workflow** to achieve high compilation success rates and discover real bugs efficiently.

---

## 🎯 Key Features

### 🏗️ **Multi-Agent Architecture**
- **Supervisor-Agent Pattern**: Central supervisor orchestrates 8 specialized agents
- **Session Memory**: Shared knowledge base for API constraints, error fixes
- **Phase-Aware Routing**: Intelligent decision-making based on compilation/optimization phases

### 🔄 **Streamlined Two-Phase Workflow**
- **Phase 1 - COMPILATION**: Function Analysis → Code Generation → Build → Error Fixing (max 3 retries)
- **Phase 2 - OPTIMIZATION**: Execution → Crash Analysis → False Positive Filtering (single-pass, no coverage iteration)

### 🧠 **Intelligent Error Handling**
- **Context-Aware Fixing**: Extracts error context (±10 lines) for targeted fixes
- **Progressive Retry**: Max 3 compilation retries with Enhancer
- **Known Fixes Memory**: Stores successful fixes in Session Memory for reuse

### 🐛 **Efficient Crash Analysis**
- **Two-Stage Validation**: Crash Analyzer (classification) + Crash Feasibility Analyzer (deep validation)
- **False Positive Filter**: Distinguishes real bugs from fuzzer harness issues
- **Severity Assessment**: Prioritizes security-relevant crashes (buffer overflow, UAF)
- **One-Shot Fix**: Single enhancer retry for false positives, then terminate

### ⚡ **Token Efficiency**
- **Session Memory Only**: No per-agent conversation history (100% memory savings)
- **Smart Context Injection**: Only top-3 relevant memories by confidence + recency
- **Optimized Prompts**: 80% token reduction through structured output

### 🔍 **FuzzingContext Data Preparation**
- **Single Source of Truth**: All data prepared once at workflow start
- **Immutable Context**: Nodes never extract data, only process provided context
- **Explicit Failures**: Missing data fails fast with clear error messages

**Supported Models:**
- OpenAI GPT (gpt-4, gpt-4o, gpt-5)
- Vertex AI Gemini (gemini-2.0-flash-exp, gemini-2-5-pro-chat)
- DeepSeek (deepseek-chat, deepseek-reasoner)
- Qwen/通义千问 (qwen-turbo, qwen-plus, qwen-max, qwen3)

---

## 🔬 Technical Highlights

### 1. **FuzzingContext: Single Source of Truth**
```python
# All data prepared ONCE at workflow start
context = FuzzingContext.prepare(project_name, function_signature)

# Immutable, shared across all agents
context.function_info      # FuzzIntrospector data
context.api_dependencies   # Call graph & sequences  
context.header_info        # Include dependencies
context.source_code        # Optional source
```

### 2. **Streamlined Error Recovery**
```python
# PHASE 1: COMPILATION (max 3 retries)
Compilation Failed → Enhancer (retry 1)
                  → Enhancer (retry 2)
                  → Enhancer (retry 3)
                  → END (give up)

# PHASE 2: OPTIMIZATION (no iteration loops)
Execution → Crash? → YES: Crash Analyzer → Crash Feasibility Analyzer
                     - Feasible (true bug)? → END (success! 🎉)
                     - False positive? → Enhancer (1 fix) → END
         → NO: Log coverage → END
```

**Key Improvements:**
- ✅ No coverage iteration loops (removed stagnation detection complexity)
- ✅ Single-pass optimization (1 enhancer fix max for false positives)
- ✅ Fast termination (no redundant build/run cycles)

### 3. **Intelligent Code Context Extraction**
```python
# Extract ±10 lines around error (targeted):
extract_error_context(error_line=142, context_lines=10)  # 20 lines
#  >>> 142 | result_t *r = target_function(data, size);
#      143 | if (r) { process_result(r); }
```

**Impact**: 95% token reduction on compilation fixes

### 4. **Session Memory (No Conversation History)**
```python
# OLD: Store full conversation history per agent (100k+ tokens)
agent_messages["prototyper"] = [msg1, msg2, msg3, ...]  # ❌ Expensive

# NEW: Session memory only (3-5 key insights)
session_memory = {
    "api_constraints": ["Must call init() before decode()"],
    "known_fixes": ["undefined reference to `compress` → Add `-lz`"],
    "archetype": "stateful_decoder"
}
```

**Impact**: 90% memory reduction, faster execution

### 5. **Two-Stage Crash Validation**
```
Crash Detected
    ↓
Crash Analyzer: "heap-buffer-overflow in parse_json:142"
    ↓
Crash Feasibility Analyzer: 
  - Is crash in target code or fuzzer harness? → Target code ✓
  - Reachable in real-world usage? → Yes (public API) ✓
  - Security-relevant? → Yes (write beyond buffer) ✓
  - Reproducible? → Yes (stable reproducer) ✓
    ↓
✅ Real Bug Found! (feasible=True) → END

OR:

Crash Feasibility Analyzer: "Timeout in harness setup" (feasible=False)
    ↓
Enhancer: Fix harness (1 attempt) → END
```

---

## 📚 Documentation

- **[WORKFLOW_DIAGRAM.md](docs/WORKFLOW_DIAGRAM.md)** - Visual diagrams of the complete workflow
- **[agent_graph/README.md](agent_graph/README.md)** - Detailed architecture and agent implementations
- **[NEW_PROJECT_SETUP.md](docs/NEW_PROJECT_SETUP.md)** - Complete guide for setting up new projects (private repos, custom codebases)
- **[Usage.md](Usage.md)** - OSS-Fuzz project quick setup guide
- **[Data Preparation](data_prep/README.md)** - Benchmark YAML generation

---

## 🚀 Quick Start

### Prerequisites

1. **LLM API Keys** (set environment variables):
   ```bash
   export OPENAI_API_KEY="sk-..."              # For GPT models
   export VERTEX_AI_PROJECT_ID="your-project" # For Gemini models
   export DEEPSEEK_API_KEY="sk-..."           # For DeepSeek models
   export QWEN_API_KEY="sk-..."               # For Qwen models
   ```

2. **Fuzz Introspector Server** (optional, recommended for better context):
   ```bash
   # Terminal 1: Start FI server (optional)
   bash report/launch_local_introspector.sh
   ```

### What LogicFuzz Does (Simple Explanation)

LogicFuzz automatically generates fuzz targets through two phases:

1. **Phase 1 - COMPILATION** (1-5 minutes):
   - Analyzes your target function's API
   - Generates a fuzz driver that calls the function
   - Compiles it with OSS-Fuzz (auto-fixes errors, max 3 retries)
   - Validates that target function is actually called

2. **Phase 2 - OPTIMIZATION** (1-5 minutes):
   - Runs the fuzzer once (default: 60 seconds)
   - If crash found → Validates if it's a real bug (two-stage analysis)
   - If no crash → Logs coverage and terminates

**Total time per function**: 2-10 minutes  
**Output**: Compiled fuzz target + coverage metrics + crashes (if found)

### 🐳 Docker Deployment

LogicFuzz provides Docker support for easy deployment and reproducibility.

#### Build Docker Image

```bash
docker build -t logicfuzz:latest .
```

#### Run Docker Container

```bash
# Basic usage
docker run --rm \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/results:/experiment/results \
  -e OPENAI_API_KEY="sk-..." \
  logicfuzz:latest \
  -b comparison \
  -m gpt-5 \
  --run-timeout 300

# With pre-built OSS-Fuzz projects (data-dir.zip)
docker run --rm \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data-dir.zip:/experiment/data-dir.zip \
  -v $(pwd)/results:/experiment/results \
  -e OPENAI_API_KEY="sk-..." \
  logicfuzz:latest \
  -b comparison \
  -m gpt-5
```

**Key Parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-b, --benchmark-set` | Benchmark set to run | `comparison` |
| `-m, --model` | LLM model name | `gpt-5` |
| `-to, --run-timeout` | Fuzzing timeout (seconds) | 300 |
| `-ns, --num-samples` | Number of LLM samples | 10 |
| `-mr, --max-round` | Max optimization rounds | 10 |

**Notes:**
- `--privileged` and Docker socket mount are required for OSS-Fuzz builds
- Mount `/experiment/results` to persist results
- Set `OPENAI_API_KEY` or `VERTEX_AI_PROJECT_ID` for LLM access

### Basic Usage (Local Installation)

```bash
# 1. Simplest: Run on first function in YAML (2-5 minutes)
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5

# What happens:
# ✓ Function Analyzer analyzes API
# ✓ Prototyper generates fuzz_driver.cc
# ✓ Build compiles with OSS-Fuzz
# ✓ Execution runs fuzzer (60s default)
# ✓ Results saved to ./results/

# 2. Target specific function (recommended)
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/libxml2.yaml \
  -f xmlParseDocument \
  --model gpt-5

# 3. With Fuzz Introspector (better API context)
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/mosh.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api

# 4. Extended fuzzing (5 samples × 5 min each = 25 min)
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/expat.yaml \
  --model gpt-5 \
  --num-samples 5 \
  --run-timeout 300

# 5. Production: Batch processing with logging
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/libpng.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --num-samples 10 \
  --run-timeout 300 \
  -w ./results \
  2>&1 | tee logicfuzz-$(date +%m%d).log

# Note: --max-round is deprecated (no iteration loops in new version)
```

### Key Parameters

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `--model` | LLM model | - | `gpt-5`, `gemini-2.0-flash-exp`, `qwen3` |
| `-e, --fuzz-introspector-endpoint` | FI server URL | None | `http://0.0.0.0:8080/api` (optional) |
| `--num-samples` | Trials per function | 5 | 5-10 (more = more diversity) |
| `--temperature` | LLM temperature | 0.4 | 0.3-0.5 (higher = more creative) |
| `--run-timeout` | Fuzzer runtime (seconds) | 60 | 60-300 (longer = more coverage) |
| `-w, --work-dir` | Output directory | `./results` | - |
| `-y, --benchmark-yaml` | Benchmark YAML file | - | Required |
| `-f, --function` | Target function name | Auto (first) | Recommended to specify |

**Deprecated Parameters** (no longer needed in optimized version):
- `--max-round` - Removed (no coverage iteration loops)

---

## 📐 Architecture Overview

LogicFuzz uses a **Supervisor-Agent Pattern** with **LangGraph-based multi-agent collaboration**:

### 🧠 Streamlined Two-Phase Workflow

```mermaid
graph TD
    %% Styles
    classDef input fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef core fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef memory fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,stroke-dasharray: 5 5;

    subgraph "Inputs"
        Config[User Config]:::input
        FI[Analysis Data]:::input
    end

    Config & FI --> Context[FuzzingContext\n(Single Source of Truth)]:::input

    subgraph "LogicFuzz Engine"
        Supervisor{Supervisor}:::core
        
        Context --> Supervisor

        Compilation[Phase 1: Compilation\n(Analyze, Generate, Fix)]:::core
        Optimization[Phase 2: Optimization\n(Execute, Validate Crashes)]:::core

        Supervisor <-->|Manage Cycle| Compilation
        Supervisor <-->|Manage Cycle| Optimization
    end

    Memory[(Session Memory)]:::memory -.->|Shared Knowledge| Compilation
    Memory -.->|Shared Knowledge| Optimization

    Supervisor --> Output[Fuzz Targets & Reports]:::input
```

### 🤖 Agent Ecosystem (6 LLM Agents + 2 Execution Nodes)

#### 🔵 Control Layer
- **Supervisor** - Phase-aware router with retry limits and session memory injection

#### 🟡 Generation Layer (LLM-Driven)
- **Function Analyzer** - API semantic analysis, archetype identification
- **Prototyper** - Initial fuzz target + build script generation
- **Enhancer** - Multi-mode fixing: compilation errors, validation errors, false positives

#### 🔴 Analysis Layer (LLM-Driven)
- **Crash Analyzer** - Crash type classification (buffer overflow, UAF, timeout)
- **Crash Feasibility Analyzer** - Deep crash validation with security assessment

#### 🟣 Execution Layer (Non-LLM)
- **Build Node** - OSS-Fuzz compilation + target function call validation
- **Execution Node** - Fuzzer execution with LLVM source-based coverage

### 🧠 Session Memory Mechanism

Cross-agent knowledge sharing system (prevents repeated mistakes):

| Memory Type | Producer | Consumer | Example |
|------------|----------|----------|---------|
| **API Constraints** | Function Analyzer | Prototyper, Enhancer | "Must call `init()` before `decode()`" |
| **Archetype** | Function Analyzer | Prototyper | "stateful_decoder", "simple_parser" |
| **Known Fixes** | Enhancer | Enhancer | "undefined reference to `compress` → Add `-lz`" |
| **Build Context** | Build Node | Enhancer | Error line ±10 context for targeted fixing |
| **Crash Context** | Crash Analyzer | Crash Feasibility Analyzer | Stack trace + ASAN report for validation |

**Injection Strategy**: Supervisor injects top-3 relevant memories (prioritized by confidence + recency) into each agent's prompt.

### 📊 Workflow Control

**Strict Retry Limits**:
- **Compilation Phase**: Max 3 enhancer retries → END
- **Validation Phase**: Max 2 enhancer retries → END
- **Optimization Phase**: Max 1 enhancer retry for false positives → END
- **Per-Node Limit**: Max 10 visits (loop prevention)

**Phase Transition Logic**:
```python
# COMPILATION → OPTIMIZATION
if compile_success and target_function_called:
    workflow_phase = "optimization"
    return "execution"

# OPTIMIZATION termination
if feasible_crash:
    return "END"  # Success!
elif not feasible_crash:
    return "fixer" (1 attempt) → "END"
elif run_success:
    return "END"  # No crash, log coverage
```

📖 **For detailed workflow implementation, see [agent_graph/README.md](agent_graph/README.md)**

---

## 📁 Project Structure

```
logicfuzz/
├── agent_graph/                    # 🧠 Multi-Agent LangGraph Workflow
│   ├── workflow.py                 # LangGraph StateGraph + FuzzingWorkflow class
│   ├── state.py                    # FuzzingWorkflowState schema + Session Memory API
│   ├── memory.py                   # Token-aware message trimming (100k per agent)
│   ├── data_context.py             # FuzzingContext (immutable data preparation)
│   ├── nodes/                      # Node implementations (LangGraph wrappers)
│   │   ├── supervisor_node.py      # Central routing logic (phase-aware)
│   │   ├── function_analyzer_node.py
│   │   ├── prototyper_node.py
│   │   ├── fixer_node.py           # Fixer node (multi-mode fixing)
│   │   ├── crash_analyzer_node.py
│   │   ├── coverage_analyzer_node.py
│   │   ├── crash_feasibility_analyzer_node.py
│   │   └── execution_node.py       # Contains both execution_node + build_node
│   ├── agents/                     # Agent implementations (LLM logic)
│   │   ├── base.py                 # Base agent class
│   │   ├── function_analyzer.py    # API semantic analysis
│   │   ├── prototyper.py           # Code generation
│   │   ├── fixer.py                # Enhancer agent (LangGraphEnhancer)
│   │   ├── crash_analyzer.py       # Crash classification
│   │   ├── coverage_analyzer.py    # Coverage analysis
│   │   ├── crash_feasibility_analyzer.py  # Crash validation
│   │   └── utils.py                # Agent utilities
│   ├── api_context_extractor.py    # API usage context from FI
│   ├── api_heuristics.py           # API pattern heuristics
│   ├── api_validator.py            # API usage validation
│   ├── header_extractor.py         # Header dependency resolution
│   ├── prompt_loader.py            # Loads prompts from prompts/
│   ├── session_memory_injector.py  # Memory injection logic
│   ├── adapters.py                 # Config adapters for agents
│   ├── benchmark_loader.py         # Benchmark YAML loader
│   └── README.md                   # Architecture deep dive
│
├── prompts/                        # 📝 LLM System Prompts (80% token optimized)
│   ├── function_analyzer_system.txt / *_prompt.txt / *_iteration_prompt.txt
│   ├── prototyper_system.txt / prototyper_prompt.txt
│   ├── fixer_system.txt / fixer_prompt.txt
│   ├── crash_analyzer_system.txt / crash_analyzer_prompt.txt
│   ├── crash_feasibility_analyzer_system.txt / crash_feasibility_analyzer_prompt.txt
│   ├── coverage_analyzer_system.txt / coverage_analyzer_prompt.txt
│   └── session_memory_header.txt / session_memory_footer.txt
│
├── experiment/                     # 🧪 Build & Evaluation Infrastructure
│   ├── builder_runner.py           # OSS-Fuzz Docker build execution + validation
│   ├── evaluator.py                # Coverage evaluation + crash detection
│   ├── textcov.py                  # LLVM source-based coverage parsing
│   ├── oss_fuzz_checkout.py        # OSS-Fuzz project checkout
│   ├── benchmark.py                # Benchmark data structures
│   ├── workdir.py                  # Working directory management
│   └── fuzz_target_error.py        # Error parsing utilities
│
├── llm_toolkit/                    # 🤖 LLM API Abstraction
│   └── models.py                   # Unified interface (OpenAI, Gemini)
│
├── data_prep/                      # 📊 Benchmark Data Preparation
│   ├── introspector.py             # FuzzIntrospector API client
│   └── project_context/            # Context extraction tools
│
├── conti-benchmark/                # 📋 Benchmark YAML Files
│   └── conti-cmp/                  # Curated benchmark suite
│
├── run_logicfuzz.py                # 🚀 Main entry point (parallel execution)
├── run_single_fuzz.py              # 🎯 Single benchmark runner
└── results.py                      # 📈 Result aggregation & reporting
```

**Key Directories**:
- `agent_graph/nodes/` - LangGraph node wrappers (state management + config extraction)
- `agent_graph/agents/` - Core LLM agent logic (prompt construction + response parsing)
- `prompts/` - Optimized system prompts with structured examples
- `experiment/` - Build/execution/evaluation infrastructure (OSS-Fuzz integration)
- `data_prep/` - Benchmark data preparation and FuzzIntrospector integration

---

## 🎓 Advanced Usage Examples

### 1. Single Function Fuzzing
```bash
# Target a specific function in a project
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/libxml2.yaml \
  -f xmlParseDocument \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --num-samples 3
```

### 2. Batch Processing
```bash
# Process all functions in a benchmark YAML
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --num-samples 10
```

### 3. Extended Fuzzing Time
```bash
# Longer fuzzing time for deeper exploration
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/expat.yaml \
  -f XML_ResumeParser \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --run-timeout 600 \
  --num-samples 5

# Note: No --max-round needed (single-pass optimization)
```

### 4. Bug Hunting Mode
```bash
# Focus on crash discovery with extended fuzzing time + multiple samples
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/libpng.yaml \
  --model gpt-5 \
  -e http://0.0.0.0:8080/api \
  --run-timeout 1800 \
  --num-samples 10 \
  --temperature 0.6

# Strategy: More samples = more diverse fuzz targets
```

### 5. Local Development (No FI Server)
```bash
# Works without Fuzz Introspector (reduced context quality)
python run_logicfuzz.py --agent \
  -y conti-benchmark/conti-cmp/cjson.yaml \
  --model gpt-5 \
  --num-samples 3
```

### 7. Custom Project Setup

For setting up your own projects (private repos, custom codebases), see:
- **[NEW_PROJECT_SETUP.md](docs/NEW_PROJECT_SETUP.md)** - Complete step-by-step guide
- **[Data Preparation](data_prep/README.md)** - Benchmark YAML generation

---

## 🎨 Design Principles

LogicFuzz is built on these core principles:

### 1. **Fail Fast, Fail Explicitly** ❌
- Missing data raises `ValueError`, not returns `None`
- No silent fallbacks that hide problems
- Clear error messages pointing to root cause

### 2. **Single Source of Truth** 📍
- All data prepared once in `FuzzingContext`
- Nodes consume context, never extract
- Immutable data prevents state pollution

### 3. **Token Efficiency First** 💰
- **No conversation history** (session memory only)
- Intelligent context extraction (±10 lines around errors)
- Session Memory prioritization (top-3 by confidence + recency)
- 90% reduction vs naive full-history approaches

### 4. **Aggressive Termination** 🔄
- **Compilation**: 3 retries → END (no regeneration)
- **Validation**: 2 retries → END
- **Optimization**: Single-pass (no iteration loops)
- **False Positives**: 1 fix → END
- Result: Faster execution, lower token cost

### 5. **Agent Specialization** 🎯
- Each agent has ONE clear responsibility
- Supervisor coordinates, doesn't generate
- Analyzers suggest, Enhancer implements

### 6. **Phase-Aware Workflow** 🚦
- **COMPILATION**: Focus on build success (max 3 retries)
- **OPTIMIZATION**: Single execution → crash analysis OR log coverage → END
- No iteration loops in optimization phase

### 7. **Real Bugs Matter** 🐛
- Two-stage validation (Crash Analyzer + Crash Feasibility Analyzer)
- False positive filtering with single fix attempt
- Security-relevant crash prioritization
---

## 📊 Performance Notes

\* "Total project lines" measures the source code of the project-under-test compiled and linked by the preexisting human-written fuzz targets from OSS-Fuzz.

\* "Total coverage gain" is calculated using a denominator of the "Total project lines". "Total relative gain" is the increase in coverage compared to the old number of covered lines.

\* Additional code from the project-under-test maybe included when compiling the new fuzz targets and result in high percentage gains.
