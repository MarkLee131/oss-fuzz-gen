# LogicFuzz Documentation Index

**Complete documentation for LogicFuzz framework - November 2024 Update**

---

## 🚀 Getting Started

### Quick Start
- **[README.md](README.md)** - Main documentation, features, quick start guide
- **[UPDATES_SUMMARY.md](UPDATES_SUMMARY.md)** - Quick summary of recent framework optimizations
- **[Usage.md](Usage.md)** - OSS-Fuzz project setup guide

### Installation & Setup
- **[docs/NEW_PROJECT_SETUP.md](docs/NEW_PROJECT_SETUP.md)** - Complete guide for setting up new projects
- **[data_prep/README.md](data_prep/README.md)** - Benchmark YAML generation

---

## 🏗️ Architecture

### Core Architecture
- **[agent_graph/README.md](agent_graph/README.md)** - ⭐ Detailed architecture documentation
  - Multi-agent workflow
  - State management
  - Agent implementations
  - Design decisions

### Workflow Diagrams
- **[docs/WORKFLOW_DIAGRAM.md](docs/WORKFLOW_DIAGRAM.md)** - ⭐ Visual workflow diagrams
  - High-level architecture
  - Phase-by-phase breakdowns
  - Agent interaction flows
  - Decision trees
  - Token flow analysis

---

## 📚 Technical Documentation

### Prompts & Templates
- **[prompts/README.md](prompts/README.md)** - LLM system prompts documentation
- **[prompts/](prompts/)** - All system prompt files
  - `function_analyzer_system.txt`
  - `prototyper_system.txt`
  - `fixer_system.txt`
  - `crash_analyzer_system.txt`
  - `crash_feasibility_analyzer_system.txt`

### Tools & Utilities
- **[docs/TOOLS_OVERVIEW.md](docs/TOOLS_OVERVIEW.md)** - Overview of supporting tools

---

## 📝 Changelog & Updates

### Recent Updates
- **[UPDATES_SUMMARY.md](UPDATES_SUMMARY.md)** - Quick summary of framework optimizations
- **[docs/CHANGELOG_2024.md](docs/CHANGELOG_2024.md)** - Detailed changelog with metrics

### Key Changes (November 2024)
1. ✅ Removed coverage iteration loops (60-70% faster)
2. ✅ Session memory only (90% memory reduction)
3. ✅ Aggressive termination strategy (clearer error messages)
4. ✅ Enhanced crash validation (better false positive filtering)
5. ✅ Added Qwen model support (qwen-turbo, qwen-plus, qwen-max, qwen3)

---

## 🎯 Use Cases & Examples

### Basic Examples
```bash
# 1. Simplest: Run on first function
python run_logicfuzz.py --agent -y conti-benchmark/conti-cmp/cjson.yaml --model gpt-5

# 2. Target specific function
python run_logicfuzz.py --agent -y conti-benchmark/conti-cmp/libxml2.yaml -f xmlParseDocument --model gpt-5

# 3. With Fuzz Introspector
python run_logicfuzz.py --agent -y conti-benchmark/conti-cmp/mosh.yaml --model gpt-5 -e http://0.0.0.0:8080/api
```

### Advanced Examples
```bash
# Extended fuzzing time (30 minutes per sample)
python run_logicfuzz.py --agent -y benchmark.yaml --model gpt-5 --run-timeout 1800 --num-samples 5

# Bug hunting mode (multiple samples, long runtime)
python run_logicfuzz.py --agent -y benchmark.yaml --model gpt-5 --run-timeout 600 --num-samples 10

# Using Qwen models
python run_logicfuzz.py --agent -y benchmark.yaml --model qwen3
```

---

## 🔬 Experimental Features

### Experimental Modules
- **[experimental/build_generator/README.md](experimental/build_generator/README.md)** - Build script generation experiments
- **[experimental/from_scratch/README.md](experimental/from_scratch/README.md)** - From-scratch fuzzer generation
- **[experimental/end_to_end/README.md](experimental/end_to_end/README.md)** - End-to-end workflow experiments

### Long-term Memory
- **[long_term_memory/README.md](long_term_memory/README.md)** - Cross-project API pattern learning (experimental)

---

## 📊 Performance & Metrics

### Token Usage (per trial)
| Component | Tokens | Notes |
|-----------|--------|-------|
| Function Analysis | 5-10k | API analysis |
| Prototyper | 8-15k | Code generation |
| Enhancer (compilation) | 6-15k | 2-3 retries typical |
| Crash Analysis | 5-10k | If crash detected |
| Session Memory | 0.5-1k | Injected into prompts |
| **Total** | **25-50k** | Success case |

### Execution Time (per trial)
| Phase | Time | Notes |
|-------|------|-------|
| Compilation | 3-8 min | Function analysis + build |
| Optimization | 1-5 min | Single execution |
| **Total** | **4-13 min** | End-to-end |

### Improvements (vs Previous Version)
- 💰 **70-80% token cost reduction**
- ⏱️ **60-70% execution time reduction**
- 💾 **90% memory usage reduction**
- 🎯 **Maintained bug-finding effectiveness**

---

## 🔧 Configuration

### LLM Models Supported
- **OpenAI GPT**: `gpt-4`, `gpt-4o`, `gpt-5`
- **Vertex AI Gemini**: `gemini-2.0-flash-exp`, `gemini-2-5-pro-chat`
- **DeepSeek**: `deepseek-chat`, `deepseek-reasoner`
- **Qwen** ✨: `qwen-turbo`, `qwen-plus`, `qwen-max`, `qwen3`

### Environment Variables
```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Google Vertex AI
export VERTEX_AI_PROJECT_ID="your-project"
export VERTEX_AI_LOCATIONS="us-central1"

# DeepSeek
export DEEPSEEK_API_KEY="sk-..."

# Qwen (Alibaba Cloud)
export QWEN_API_KEY="sk-..."
```

### Key Parameters
| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `--model` | LLM model | - | `gpt-5`, `qwen3` |
| `-e, --fuzz-introspector-endpoint` | FI server URL | None | `http://0.0.0.0:8080/api` |
| `--num-samples` | Trials per function | 5 | 5-10 |
| `--temperature` | LLM temperature | 0.4 | 0.3-0.5 |
| `--run-timeout` | Fuzzer runtime (seconds) | 60 | 60-300 |
| `-w, --work-dir` | Output directory | `./results` | - |

**Deprecated**:
- `--max-round` - No longer needed (no iteration loops)

---

## 🎨 Design Principles

1. **Fail Fast, Fail Explicitly** - No silent fallbacks, clear error messages
2. **Single Source of Truth** - All data prepared once in `FuzzingContext`
3. **Token Efficiency First** - 90% memory reduction, session memory only
4. **Aggressive Termination** - Strict retry limits (compilation: 3, validation: 2)
5. **Agent Specialization** - Each agent has one clear responsibility
6. **Phase-Aware Workflow** - Different strategies for compilation vs optimization
7. **Real Bugs Matter** - Two-stage crash validation, false positive filtering

---

## 🐛 Troubleshooting

### Common Issues

**Compilation Fails After 3 Retries**
- Check if library is available in OSS-Fuzz
- Verify target function signature is correct
- Review build errors in `./results/*/build_log.txt`

**Target Function Not Called**
- Verify function name in YAML matches actual code
- Check if function is static/internal (may not be accessible)
- Review validation error in state output

**No Crashes Found**
- Increase `--run-timeout` (longer fuzzing time)
- Increase `--num-samples` (more diverse targets)
- Verify function has known vulnerabilities

**Token Limit Exceeded**
- Should not happen with new optimized version
- If it does, please report as bug

---

## 📞 Support & Contributing

### Getting Help
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Start with this index
- **Examples**: See `conti-benchmark/conti-cmp/*.yaml`

### Contributing
- Follow existing code style
- Update documentation for new features
- Add tests for agent changes
- Update prompts/ for LLM changes

---

## 📄 License

Apache 2.0 License - See [LICENSE](LICENSE) file for details

---

## 🔗 Quick Links

### Essential Docs
- [Main README](README.md) - Start here
- [Architecture](agent_graph/README.md) - Understand the system
- [Workflow Diagrams](docs/WORKFLOW_DIAGRAM.md) - Visual guides
- [Updates Summary](UPDATES_SUMMARY.md) - What changed

### Setup Guides
- [Quick Start](Usage.md) - Get started fast
- [New Project Setup](docs/NEW_PROJECT_SETUP.md) - Add custom projects
- [Data Preparation](data_prep/README.md) - Generate benchmarks

### Technical Deep Dives
- [Changelog](docs/CHANGELOG_2024.md) - Detailed changes
- [Prompts](prompts/README.md) - LLM system prompts
- [Tools Overview](docs/TOOLS_OVERVIEW.md) - Supporting utilities

---

**Last Updated**: November 2024  
**Documentation Version**: 2.0  
**Framework Version**: 2.0 (Optimized Release)

