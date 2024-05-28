"""
used to test the prompts
"""
import json

with open(
    '/home/kaixuan/FDG_LLM/oss-fuzz-gen/results/output-jsonnet-_zn7jsonnet8internal12_global__n_111interpreter13builtinextvarerkns0_13locationrangeerknst3__16vectorins1/prompt.txt',
    'r') as f:
  prompts = json.load(f)

for prompt in prompts:
  print(prompt['role'])
  print(prompt['content'])
