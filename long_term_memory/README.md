# Long-term Memory Knowledge Base

## Overview

This directory contains structured knowledge extracted from:
- Expert-written fuzzing drivers from OSS-Fuzz
- Empirical analysis of 4,699+ production fuzzers
- Real-world fuzzing patterns and best practices

The knowledge is organized into **archetypes** - fundamental patterns for writing correct fuzz drivers. Each archetype represents a common API design pattern and provides guidance on how to fuzz it correctly.

---

## Directory Structure

```
long_term_memory/
├── archetypes/                   # 10 archetype patterns (SRS JSON format)
│   ├── object_lifecycle.srs.json
│   ├── stateful_context.srs.json
│   ├── temporary_file.srs.json
│   ├── iterative_processing.srs.json
│   ├── event_driven_state_machine.srs.json
│   ├── callback_registration.srs.json
│   ├── one_time_initialization.srs.json
│   ├── exception_handling.srs.json
│   ├── structured_input.srs.json
│   └── round_trip_testing.srs.json
│
├── retrieval.py                  # Retrieval implementation
└── README.md                     # This file
```

Each SRS JSON file contains:
- **archetype_name**: Human-readable pattern name
- **api_pattern**: High-level description of the pattern
- **when_to_use**: Conditions for applying this pattern
- **core_template**: C/C++ code skeletons
- **critical_mistakes**: Common errors with wrong/right examples
- **real_examples**: Real-world APIs using this pattern

---

## The 10 Archetypes

Archetypes are organized by their primary characteristic:

### 🔧 Resource Management

1. **`object_lifecycle`** - Most common pattern
   - Pattern: Create object → Use object → Destroy object
   - Example: `XML_ParserCreate()` → `XML_Parse()` → `XML_ParserFree()`
   - Use when: API requires explicit object initialization and cleanup
   - Critical: Must check create() return value, use goto cleanup pattern

2. **`stateful_context`** - Performance optimization
   - Pattern: Static context reused across fuzz inputs with reset
   - Example: `static ZSTD_DCtx *ctx` reused across inputs
   - Use when: Context creation is expensive (e.g., compression contexts)
   - Critical: Must reset context state between inputs to avoid contamination

3. **`temporary_file`** - File path APIs
   - Pattern: Write temp file → API loads file → Cleanup
   - Example: OpenCV `cv::imread(filename)`
   - Use when: API requires file path instead of memory buffer
   - Critical: Use unique filename, close before reading, always unlink

### 🔄 Control Flow

4. **`iterative_processing`** - Bounded loops
   - Pattern: Loop with mandatory iteration limit
   - Example: `while(max_iter-- > 0) { inflate() }`
   - Use when: API processes data in chunks/iterations
   - Critical: Must limit iterations to prevent timeout

5. **`event_driven_state_machine`** - Event loops
   - Pattern: Repeatedly drive state machine with events until completion
   - Example: curl multi-handle `curl_multi_socket_action()`
   - Use when: API is event-driven or state-machine based
   - Critical: Must cap number of steps, check running counter

### 📞 API Sequencing

6. **`callback_registration`** - Callback setup
   - Pattern: Set callbacks → Use API
   - Example: expat `XML_SetElementHandler()` → `XML_Parse()`
   - Use when: API requires callbacks before use
   - Critical: Callbacks must be set BEFORE processing starts

7. **`one_time_initialization`** - Global setup
   - Pattern: `LLVMFuzzerInitialize()` for one-time setup
   - Example: yara rule compilation, codec initialization
   - Use when: Library requires global initialization
   - Critical: Check initialization return value, use atexit() for cleanup

### ⚠️ Error Handling

8. **`exception_handling`** - C++ exceptions
   - Pattern: `try { API() } catch (...) {}`
   - Example: C++ STL, modern C++ libraries
   - Use when: API may throw exceptions
   - Critical: Must catch ALL exceptions with `catch(...)`

### 📦 Input Construction

9. **`structured_input`** - Multi-parameter APIs
   - Pattern: Use FuzzedDataProvider to split input into parameters
   - Example: `cJSON_ParseWithOpts(data, flag1, flag2)`
   - Use when: API has 3+ parameters
   - Critical: Don't use fixed parameters, vary all for better coverage

### ✅ Verification

10. **`round_trip_testing`** - Encode/decode validation
    - Pattern: Parse → Serialize → Verify equality
    - Example: protobuf unpack → pack → verify
    - Use when: API supports both parsing and serialization
    - Critical: Must test both directions, verify correctness

---

## Archetype Selection Guide

### By API Characteristics:

| API Characteristic | Archetype |
|-------------------|-----------|
| Single function, no state | `object_lifecycle` (even simple APIs need resource checks) |
| Explicit create/destroy | `object_lifecycle` |
| Requires file path | `temporary_file` |
| Has callbacks | `callback_registration` |
| Processes in loop | `iterative_processing` |
| Event-driven | `event_driven_state_machine` |
| Needs global init | `one_time_initialization` |
| Throws exceptions | `exception_handling` |
| Many parameters | `structured_input` |
| Parse + serialize | `round_trip_testing` |
| Expensive context | `stateful_context` |

### Decision Tree:

```
Does API throw C++ exceptions?
├─ Yes → exception_handling (wrap in try-catch)
└─ No
    Does API require file path (not memory)?
    ├─ Yes → temporary_file
    └─ No
        Does API have expensive context creation?
        ├─ Yes → stateful_context (reuse across inputs)
        └─ No
            Does API require global initialization?
            ├─ Yes → one_time_initialization (LLVMFuzzerInitialize)
            └─ No
                Does API support both parse and serialize?
                ├─ Yes → round_trip_testing
                └─ No
                    Does API require callbacks?
                    ├─ Yes → callback_registration
                    └─ No
                        Does API process in loop/iterations?
                        ├─ Yes → iterative_processing
                        └─ No
                            Is API event-driven/state machine?
                            ├─ Yes → event_driven_state_machine
                            └─ No
                                Does API have 3+ parameters?
                                ├─ Yes → structured_input
                                └─ No → object_lifecycle (default)
```

---

## SRS JSON Format

Each archetype is stored as a unified SRS (Software Requirements Specification) JSON file:

```json
{
  "archetype_name": "object_lifecycle",
  "api_pattern": "Create object → Use object → Destroy object",
  "when_to_use": [
    "API requires object initialization before use",
    "Object must be explicitly destroyed/cleaned up"
  ],
  "core_template": {
    "c": "...",
    "cpp": "..."
  },
  "critical_mistakes": [
    {
      "mistake": "Not checking create() return value",
      "wrong": "...",
      "right": "...",
      "why": "..."
    }
  ],
  "real_examples": [
    "expat: XML_ParserCreate() → XML_Parse() → XML_ParserFree()"
  ]
}
```

### Critical Mistakes Format

Each mistake includes:
- **mistake**: Description of the error
- **wrong**: Code example showing the mistake
- **right**: Correct code example
- **why**: Explanation of why it matters

This format enables LLMs to learn from concrete examples.

---

## Retrieval API

```python
from long_term_memory.retrieval import KnowledgeRetriever

retriever = KnowledgeRetriever()

# List all available archetypes
archetypes = retriever.list_archetypes()
# Returns: ['object_lifecycle', 'stateful_context', ...]

# Get archetype description (markdown format)
archetype_doc = retriever.get_archetype("object_lifecycle")
# Returns: Formatted markdown describing the pattern

# Get code skeleton
skeleton = retriever.get_skeleton("object_lifecycle", language="c")
# Returns: C/C++ code template

# Get critical mistakes
pitfalls = retriever.get_pitfalls("object_lifecycle")
# Returns: Formatted text with wrong/right examples

# Get full SRS JSON
srs = retriever.get_srs("object_lifecycle")
# Returns: Complete SRS JSON as dict

# Get everything (convenience method)
bundle = retriever.get_bundle("object_lifecycle")
# Returns: {
#   'archetype': '<markdown description>',
#   'skeleton': '<C code>',
#   'pitfalls': {'critical_mistakes': '<formatted text>'},
#   'srs': <full SRS JSON dict>
# }
```

### Quick Access Functions

```python
from long_term_memory.retrieval import get_archetype_bundle, get_skeleton_code, get_srs

# Quick access without creating retriever
bundle = get_archetype_bundle("object_lifecycle")
skeleton = get_skeleton_code("object_lifecycle")
srs = get_srs("object_lifecycle")
```

---

## Usage in Workflow

### Stage 1: Function Analyzer

When analyzing target functions, retrieve archetype knowledge to guide specification:

```python
from long_term_memory.retrieval import KnowledgeRetriever

retriever = KnowledgeRetriever()

# Get archetype description for context
archetype_doc = retriever.get_archetype("object_lifecycle")

# Inject into Function Analyzer prompt
context = f"""
Relevant Pattern:
{archetype_doc}

When writing the specification, follow this pattern.
Identify the create, use, and destroy operations.
"""
```

### Stage 2: Prototyper

When generating fuzz drivers, retrieve skeleton and pitfalls:

```python
from long_term_memory.retrieval import KnowledgeRetriever

retriever = KnowledgeRetriever()

# Get full bundle
bundle = retriever.get_bundle("object_lifecycle")

# Inject into Prototyper prompt
prompt = f"""
Base skeleton:
{bundle['skeleton']}

Critical mistakes to avoid:
{bundle['pitfalls']['critical_mistakes']}

Generate driver following the skeleton and avoiding the mistakes.
"""
```

---

## Maintenance

### Adding New Archetypes

1. Create `archetypes/new_pattern.srs.json` following the SRS JSON format
2. Add archetype name to `KnowledgeRetriever.ARCHETYPES` list in `retrieval.py`
3. Test with: `python retrieval.py`

### Updating Existing Archetypes

- Edit the corresponding `.srs.json` file directly
- Update `critical_mistakes` based on observed failures
- Add new `real_examples` from recent projects
- Keep `core_template` up to date with best practices

### JSON Schema

All archetype JSON files must include:
- `archetype_name` (string)
- `api_pattern` (string)
- `when_to_use` (array of strings)
- `core_template` (object with "c" and/or "cpp" keys)
- `critical_mistakes` (array of objects with mistake/wrong/right/why)
- `real_examples` (array of strings)

---

## Statistics

Current knowledge base:
- **10 archetypes** covering 95%+ of fuzzing scenarios
- **10 code skeletons** (C and C++ versions)
- **40+ critical mistakes** documented with examples
- **50+ real-world examples** from production fuzzers

Knowledge extracted from:
- 4,699+ OSS-Fuzz production drivers
- Manual analysis of expert-written drivers
- Empirical fuzzing research

Archetype coverage:
- `object_lifecycle`: ~60% of APIs (most common)
- `stateful_context`: ~10% (performance-critical)
- `round_trip_testing`: ~8% (serialization APIs)
- Others: ~22% (specialized patterns)

---

## Benefits

### For Function Analyzer
- Quick reference for pattern identification
- Real examples to cite in specifications
- Clear requirements and constraints

### For Prototyper
- Ready-made code skeletons
- Proven implementation patterns
- Common pitfalls to avoid

### For Quality
- Consistent driver structure
- Fewer common errors
- Better coverage through proper patterns

---

## Archetype Design Principles

1. **Mutually Exclusive**: Each archetype addresses a distinct API pattern
2. **Practically Useful**: Based on real-world fuzzing needs, not theoretical
3. **Actionable**: Provides concrete implementation guidance
4. **Evidence-Based**: Derived from analysis of thousands of production drivers
5. **Mistake-Aware**: Documents common errors with examples
6. **Composable**: Archetypes can be combined (e.g., object_lifecycle + exception_handling)
