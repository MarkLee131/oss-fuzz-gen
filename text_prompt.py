"""
used to test the prompts
"""
import json

with open(
    '/home/kaixuan/FDG_LLM/oss-fuzz-gen/results/\
      output-openssl-ossl_cmp_ctx_server_perform/prompt.txt', 'r') as f:
  prompts = json.load(f)

for prompt in prompts:
  print(prompt['role'])
  print(prompt['content'])
