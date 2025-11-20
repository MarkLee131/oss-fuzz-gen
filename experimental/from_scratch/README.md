# Quick Harness Generation for Local Codebases

**Purpose:** Fast prototyping tool for generating fuzz harnesses without OSS-Fuzz integration

## 🎯 When to Use This Tool

**Use `experimental.from_scratch.generate` when:**
- You're developing locally and need a quick harness for testing
- You don't need full OSS-Fuzz integration (Docker, build scripts, etc.)
- You want to iterate quickly on harness ideas
- You're testing a specific function in your codebase

**Don't use this tool if:**
- You want a complete OSS-Fuzz project → Use `oss-fuzz-generator generate-full` instead
- You need coverage reports and crash analysis → Use `run_logicfuzz.py` instead
- You're submitting to OSS-Fuzz → Use `oss-fuzz-generator` for proper integration

## 🔍 Comparison with Other Tools

| Feature | `from_scratch` (This Tool) | `oss-fuzz-generator` | `run_logicfuzz.py` |
|---------|---------------------------|-------------------|-------------------|
| **Output** | Single harness file | Complete OSS-Fuzz project | Fuzz targets + reports |
| **Requires OSS-Fuzz** | ❌ No | ✅ Yes (creates it) | ✅ Yes (must exist) |
| **Docker integration** | ❌ No | ✅ Yes | ✅ Yes |
| **Coverage reports** | ❌ No | ✅ Yes | ✅ Yes |
| **Speed** | ⚡ Very fast | 🐢 Slow | 🐌 Slow |
| **Build scripts** | ❌ Not generated | ✅ Generated | ❌ Uses existing |
| **Best for** | Local dev/testing | Production onboarding | Evaluation/research |

**Key Difference:** This tool generates **just the harness code** - you'll need to compile and run it yourself. Other tools handle the full OSS-Fuzz integration pipeline.

---

To run this you need a local version of Fuzz Introspector (optional) and a target code
base you want to analyse.

## Setting up

The first step is to create a virtual environment with Fuzz Introspector
installed and also logicfuzz dependencies installed. The following
commands achieve this:

```sh
# Create virtual environment
python3.11 -m virtualenv .venv
. .venv/bin/activate

# Install Fuzz Introspector in virtual environment
git clone https://github.com/ossf/fuzz-introspector
cd fuzz-introspector/src
python3 -m pip install .
cd ../../

# Clone logicfuzz and install dependencies
# Clone logicfuzz
git clone https://github.com/MarkLee131/logicfuzz
cd logicfuzz
python3 -m pip install -r ./requirements.txt
```

## Run harness generation on C code

Sample run where `${MODEL}` holds your model name:

Perform the following operations from inside the logicfuzz repository
at the root of the repository. In this example, we generate a target based
on the function name of the target function.

```sh
# Prepare a target
git clone https://github.com/dvhar/dateparse ../dateparse

# Generate a harness with function name
python3 -m experimental.from_scratch.generate \
  -l c++ \
  -m ${MODEL} \
  -f dateparse \
  -t ../dateparse/ \
  -o out_cpp

# Show harness
cat out_cpp/01.rawoutput
"""
#include <stdio.h>
#include <string.h>

typedef struct{int year;int month; int day;} date_t;

int dateparse(const char* datestr, date_t* t, int *offset, int stringlen); // prototype

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    date_t t;
    int offset = 0;
    
    // ensure NULL termination for the data string
    char* datestr = (char*)malloc(size + 1);
    if (!datestr)
        return 0;
    memcpy(datestr, data, size);
    datestr[size] = '\0';
    
    dateparse(datestr, &t, &offset, size);

    free(datestr);
    return 0;
}
"""
```