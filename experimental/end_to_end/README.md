# End-to-End OSS-Fuzz Project Generation

**Purpose:** Complete pipeline for generating OSS-Fuzz projects from GitHub repositories

This module provides the `oss-fuzz-generator` CLI tool that automates the entire process of onboarding new projects to OSS-Fuzz, from build script generation to fuzz harness creation.

## 🎯 When to Use This Tool

**Use `oss-fuzz-generator` when:**
- You want to onboard a new GitHub repository to OSS-Fuzz
- You need to generate build scripts (Dockerfile + build.sh) for a project
- You want a complete, validated OSS-Fuzz integration
- You need to fix failing OSS-Fuzz builds automatically

**Don't use this tool if:**
- You already have an OSS-Fuzz project setup → Use `run_logicfuzz.py` instead
- You just need a quick harness for local testing → Use `experimental.from_scratch.generate` instead

## 🏗️ Architecture

This end-to-end module is a **CLI wrapper** around two core libraries:

```
oss-fuzz-generator CLI
├── generate-builds     → calls experimental.build_generator.runner
├── fix-build          → calls experimental.build_fixer.build_fix  
├── generate-harnesses → calls run_logicfuzz.py workflow
└── generate-full      → combines all of the above
```

**Bottom Line:** This is the **user-friendly interface**. The actual implementation is in `experimental/build_generator/` and `experimental/build_fixer/`.

---

Tools for generating a fuzzing infrastructure that has been validated and
tested from scratch, for a given GitHub repository. That is, this tool
takes as input a project URL and outputs a set of OSS-Fuzz projects
with fuzzing harnesses.

## Usage

To run OSS-Fuzz project generation a CLI tool is exposed from
installing logicfuzz in a Python virtual environment. This is installed
using the following command:

```sh
# Set up virtual environment
python3.11 -m virtualenv .venv
. .venv/bin/activate

# Clone and install LogicFuzz
python3 -m pip install .
```

Upon installation of LogicFuzz in the Python environment,
a CLI tool `oss-fuzz-generator` is made available that has
the following `help`:

```sh
$ oss-fuzz-generator --help
usage: oss-fuzz-generator [-h] {generate-builds,generate-fuzz-introspector-database,generate-harnesses,generate-full} ...

positional arguments:
  {generate-builds,generate-fuzz-introspector-database,generate-harnesses,generate-full}
    generate-builds     Generate OSS-Fuzz projects with build scripts but empty fuzzers.
    generate-fuzz-introspector-database
                        Generates a fuzz introspector database from auto build projects.
    generate-harnesses  Harness generation of OSS-Fuzz projects.
    generate-full       Generate OSS-Fuzz integration from git URLs.

options:
  -h, --help            show this help message and exit

```

`oss-fuzz-generator` makes several commands available, and the following
will iterate over these tools:


### End to end generation

**Generating OSS-Fuzz projects for a single repository**
The following example shows how to run the complete process of an 
OSS-Fuzz project generation.

```sh
# Use installed binary oss-fuzz-generator to create OSS-Fuzz project
oss-fuzz-generator generate-full -m ${MODEL} -i "https://github.com/kgabis/parson
...
$ ls final-oss-fuzz-projects/parson-agent/
build.sh  Dockerfile  empty-fuzzer.0.c  empty-fuzzer.1.c  empty-fuzzer.2.c  empty-fuzzer.3.c  empty-fuzzer.4.c  project.yaml
```

**Generating OSS-Fuzz projects for multiple repositories**

OSS-Fuzz generation can also be applied to a list of repositories by
using a file with a list of URLs to the repositories:

```sh
$ cat input.txt 
https://github.com/zserge/jsmn
https://github.com/rafagafe/tiny-json
$ oss-fuzz-generator generate-full -m ${MODEL} -i input.txt
$ tree final-oss-fuzz-projects/
final-oss-fuzz-projects/
├── jsmn-agent
│   ├── build.sh
│   ├── Dockerfile
│   ├── empty-fuzzer.0.c
│   ├── empty-fuzzer.1.c
│   ├── empty-fuzzer.2.c
│   ├── empty-fuzzer.3.c
│   ├── empty-fuzzer.4.c
│   ├── empty-fuzzer.5.c
│   ├── empty-fuzzer.6.c
│   ├── empty-fuzzer.7.c
│   └── project.yaml
└── tiny-json-agent
    ├── build.sh
    ├── Dockerfile
    ├── empty-fuzzer.0.c
    ├── empty-fuzzer.10.c
    ├── empty-fuzzer.11.c
    ├── empty-fuzzer.1.c
    ├── empty-fuzzer.2.c
    ├── empty-fuzzer.3.c
    ├── empty-fuzzer.4.c
    ├── empty-fuzzer.5.c
    ├── empty-fuzzer.6.c
    ├── empty-fuzzer.7.c
    ├── empty-fuzzer.8.c
    ├── empty-fuzzer.9.c
    └── project.yaml

2 directories, 26 files
```


---

## 🔍 Comparison with Other LogicFuzz Tools

### vs. `run_logicfuzz.py` (Main Workflow)

| Feature | `oss-fuzz-generator` (This Tool) | `run_logicfuzz.py` |
|---------|-------------------------------|-------------------|
| **Input** | GitHub repository URL | Benchmark YAML file |
| **Output** | Complete OSS-Fuzz project | Fuzz targets only |
| **Generates build scripts** | ✅ Yes (Dockerfile + build.sh) | ❌ No (uses existing) |
| **Generates harnesses** | ✅ Yes | ✅ Yes |
| **Use case** | New project onboarding | Existing OSS-Fuzz projects |
| **Prerequisites** | GitHub URL | OSS-Fuzz project must exist |

**Example Decision:**
- "I want to add `mylib` to OSS-Fuzz" → Use `oss-fuzz-generator generate-full`
- "I want better harnesses for existing `libxml2` project" → Use `run_logicfuzz.py`

### vs. `experimental.from_scratch.generate`

| Feature | `oss-fuzz-generator` | `from_scratch` |
|---------|-------------------|----------------|
| **Output** | Full OSS-Fuzz project | Single harness file |
| **Docker integration** | ✅ Yes | ❌ No |
| **Build scripts** | ✅ Generated | ❌ Not needed |
| **OSS-Fuzz compatible** | ✅ Yes | ❌ No |
| **Speed** | 🐢 Slow (complete pipeline) | ⚡ Fast (single file) |
| **Use case** | Production onboarding | Quick local testing |

**Example Decision:**
- "I'm submitting to OSS-Fuzz" → Use `oss-fuzz-generator`
- "I'm testing a function locally" → Use `from_scratch`

---

## 📚 Related Documentation

- **Tool Comparison:** See [docs/TOOLS_OVERVIEW.md](../../docs/TOOLS_OVERVIEW.md) for complete tool hierarchy
- **Main Workflow:** See [README.md](../../README.md) for `run_logicfuzz.py` usage
- **From Scratch:** See [experimental/from_scratch/README.md](../from_scratch/README.md) for local harness generation
- **Build Generation Library:** See [experimental/build_generator/README.md](../build_generator/README.md)
- **Build Fixing Library:** See [experimental/build_fixer/](../build_fixer/) (no README yet)

---

# Trophies

Here we list a set of trophies based of this approach. Since we generate both
OSS-Fuzz and ClusterFuzzLite integrations we highlight for each trophy which
type was submitted to the upstream repository.

| GitHub repository | Type | PR | Issues |
| ----------------- | ---- | -- | ------ |
| https://github.com/gregjesl/simpleson | ClusterFuzzLite | [40](https://github.com/gregjesl/simpleson/pull/40) | [39](https://github.com/gregjesl/simpleson/pull/39) |
| https://github.com/memononen/nanosvg | OSS-Fuzz | [11944](https://github.com/google/oss-fuzz/pull/11944) | |
| https://github.com/skeeto/pdjson | ClusterFuzzLite | [33](https://github.com/skeeto/pdjson/pull/33)  | |
| https://github.com/kgabis/parson | ClusterFuzzLite | [214](https://github.com/kgabis/parson/pull/214) | |
| https://github.com/rafagafe/tiny-json | ClusterFuzzLite | [18](https://github.com/rafagafe/tiny-json/pull/18) | |
| https://github.com/kosma/minmea | ClusterFuzzLite | [79](https://github.com/kosma/minmea/pull/79) | |
| https://github.com/marcobambini/sqlite-createtable-parser | ClusterFuzzLite | [5](https://github.com/marcobambini/sqlite-createtable-parser/pull/5) | [6](https://github.com/marcobambini/sqlite-createtable-parser/pull/6) |
| https://github.com/benoitc/http-parser | ClusterFuzzLite | [102](https://github.com/benoitc/http-parser/pull/102) | [103](https://github.com/benoitc/http-parser/pull/103) |
| https://github.com/orangeduck/mpc | ClusterFuzzLite | [169](https://github.com/orangeduck/mpc/pull/169) | |
| https://github.com/JiapengLi/lorawan-parser | ClusterFuzzLite | [17](https://github.com/JiapengLi/lorawan-parser/pull/17) | |
| https://github.com/argtable/argtable3 | ClusterFuzzLite | [96](https://github.com/argtable/argtable3/pull/96) | |
| https://github.com/h2o/picohttpparser | ClusterFuzzLite | [83](https://github.com/h2o/picohttpparser/pull/83) | |
| https://github.com/ndevilla/iniparser | ClusterFuzzLite | [161](https://github.com/ndevilla/iniparser/pull/161) | |
| https://github.com/codeplea/tinyexpr | ClusterFuzzLite | [114](https://github.com/codeplea/tinyexpr/pull/114) | |
| https://github.com/vincenthz/libjson | ClusterFuzzLite | [28](https://github.com/vincenthz/libjson/pull/28) | |
