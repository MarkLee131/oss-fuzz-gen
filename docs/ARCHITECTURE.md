# LogicFuzz Architecture & Design

This document details the architectural design, technical highlights, and core principles of LogicFuzz.

## 📐 Architecture Overview

LogicFuzz uses a **Supervisor-Agent Pattern** with **LangGraph-based multi-agent collaboration**.

### Streamlined Two-Phase Workflow

The workflow is divided into two distinct phases to optimize for different goals:

1.  **Phase 1: Compilation** (Analyze, Generate, Fix)
    *   Goal: Successfully compile a fuzz target that calls the target function.
    *   Strategy: Fast failure with strict retry limits.
2.  **Phase 2: Optimization** (Execute, Validate)
    *   Goal: Execute the fuzzer, find crashes, and validate them.
    *   Strategy: Single-pass execution (no coverage loops) with deep crash validation.

### 🤖 Agent Ecosystem

#### 🔵 Control Layer
*   **Supervisor**: Phase-aware router with retry limits and session memory injection.

#### 🟡 Generation Layer (LLM-Driven)
*   **Function Analyzer**: API semantic analysis, archetype identification.
*   **Prototyper**: Initial fuzz target + build script generation.
*   **Enhancer**: Multi-mode fixing (compilation, validation, false positives).

#### 🔴 Analysis Layer (LLM-Driven)
*   **Crash Analyzer**: Crash type classification (buffer overflow, UAF, timeout).
*   **Crash Feasibility Analyzer**: Deep crash validation with security assessment.

#### 🟣 Execution Layer (Non-LLM)
*   **Build Node**: OSS-Fuzz compilation + target function call validation.
*   **Execution Node**: Fuzzer execution with LLVM source-based coverage.

---

## 🔬 Technical Highlights

### 1. FuzzingContext: Single Source of Truth
All data is prepared ONCE at the workflow start. Nodes consume this context but never modify it or extract data themselves.

```python
# All data prepared ONCE at workflow start
context = FuzzingContext.prepare(project_name, function_signature)

# Immutable, shared across all agents
context.function_info      # FuzzIntrospector data
context.api_dependencies   # Call graph & sequences  
context.header_info        # Include dependencies
context.source_code        # Optional source
```

### 2. Session Memory (No Conversation History)
Instead of maintaining full conversation history (which is expensive and redundant), LogicFuzz uses a "Session Memory" that stores key insights.

**Impact**: 90% memory reduction.

```python
# Key insights only (3-5 items)
session_memory = {
    "api_constraints": ["Must call init() before decode()"],
    "known_fixes": ["undefined reference to `compress` → Add `-lz`"],
    "archetype": "stateful_decoder"
}
```

### 3. Intelligent Code Context Extraction
When compilation fails, only the relevant error context (±10 lines) is sent to the LLM, rather than the full file.

**Impact**: 95% token reduction on compilation fixes.

### 4. Two-Stage Crash Validation
To distinguish real bugs from fuzzer harness issues:

1.  **Crash Analyzer**: Classifies the crash (e.g., "heap-buffer-overflow").
2.  **Crash Feasibility Analyzer**: Validates:
    *   Is it in target code or harness?
    *   Is it reachable in real-world usage?
    *   Is it security-relevant?

---

## 🎨 Design Principles

1.  **Fail Fast, Fail Explicitly** ❌
    *   Missing data raises `ValueError`, not silent failures.
    *   Clear error messages pointing to root causes.

2.  **Single Source of Truth** 📍
    *   Immutable `FuzzingContext` prevents state pollution.

3.  **Token Efficiency First** 💰
    *   No conversation history (session memory only).
    *   Intelligent context extraction.

4.  **Aggressive Termination** 🔄
    *   **Compilation**: Max 3 retries.
    *   **Validation**: Max 2 retries.
    *   **Optimization**: Single-pass (no iteration loops).
    *   **False Positives**: 1 fix attempt.

5.  **Agent Specialization** 🎯
    *   Each agent has ONE clear responsibility.

6.  **Real Bugs Matter** 🐛
    *   Focus on security-relevant crashes and false positive filtering.

---

## 📚 Further Reading

*   **[Agent Graph Implementation](../agent_graph/README.md)**: Deep dive into the code and agent logic.
*   **[Workflow Diagrams](WORKFLOW_DIAGRAM.md)**: Visual representations of the workflow.

