"""
Filter out useless APIs (no/little need to be fuzzed) from the API list within the benchmark.

Now we prompt GPT-4o to check the usefulness of each API in the benchmark.
"""
import os
import requests

# Configuration for Azure GPT-4o

API_KEY = os.getenv("AZURE_OPENAI_API_KEY", '')

ENDPOINT = os.getenv("AZURE_OPENAI_API_ENDPOINT", '')
assert (ENDPOINT, "Please set the API endpoint as an environment variable 'AZURE_OPENAI_API_ENDPOINT'.")

BENCHMARK_ROOT_DIR = "/home/kaixuan/FDG_LLM/oss-fuzz-gen/benchmark-sets/all"





headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

# Payload for the request
payload = {
    "messages": [{
        "role":
            "system",
        "content": [
            {
            "type":
                "text",
            "text":
                "You are a Fuzz testing expert for C/C++ OSS projects. Please check the usefulness of each API in the benchmark and filter out the useless APIs (no/little need to be fuzzed)." 
        }
                    ]
    }],
    "temperature": 0,
    "top_p": 0.95,
    "max_tokens": 100
}

# Send request
try:
  response = requests.post(ENDPOINT, headers=headers, json=payload)
  
  print(response)
  
  response.raise_for_status(
  )  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
except requests.RequestException as e:
  raise SystemExit(f"Failed to make the request. Error: {e}")

# Handle the response as needed (e.g., print or process)
print(response.json())
