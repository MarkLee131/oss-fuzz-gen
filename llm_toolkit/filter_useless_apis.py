"""
Filter out useless APIs (no/little need to be fuzzed) from the API list within the benchmark.

Now we prompt GPT-4o to check the usefulness of each API in the benchmark.
"""
import os

import requests

# Configuration for Azure GPT-4o

API_KEY = os.getenv("OPENAI_API_KEY")
ENDPOINT = os.getenv(
    "OPENAI_API_ENDPOINT",
    "https://api.openai.com/v1/engines/davinci-codex/completions")

headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

# Payload for the request
payload = {
    "messages": [{
        "role":
            "system",
        "content": [{
            "type":
                "text",
            "text":
                "You are an AI assistant that helps people find information."
        }]
    }],
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 800
}

# Send request
try:
  response = requests.post(ENDPOINT, headers=headers, json=payload)
  response.raise_for_status(
  )  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
except requests.RequestException as e:
  raise SystemExit(f"Failed to make the request. Error: {e}")

# Handle the response as needed (e.g., print or process)
print(response.json())
