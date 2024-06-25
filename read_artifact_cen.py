import json
import os

DIR = '/home/kaixuan/FDG_LLM/artifacts-llm4fdg/jsons/'

with open(
    os.path.join(
        DIR,
        'query_results_validated_repeated_all_gpt4_NAIVE_queries.json')) as f:
  data = json.load(f)

  # print(data.keys())

  ## filter the keys contain "tasks-repeat/repeat_0_a_validated_web-gpt4_BA_NAIVE_guetzli"

  for key in data.keys():
    if "tasks-repeat/repeat_0_a_validated_web-gpt4_BA_NAIVE_hiredis" in key:
      print(key)
      print(data[key]["naiveIncluded"])
      print("\n")

  # data  = data["tasks-repeat/repeat_0_a_validated_web-gpt4_BA_NAIVE_bind9_dns_master_loadbuffer.json|c-bind9-dns_master_loadbuffer-NAIVE-CHATGPT-INITIAL-0"]

  # print(data.keys())
  # print(data['id'])
  # print(data['naiveIncluded'])
