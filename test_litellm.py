import os
import sys

# Assume we already have litellm installed via hermes-agent
try:
    from litellm import completion
except ImportError:
    print("litellm not found, skipping test")
    sys.exit(0)

# Load config to get API key
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import Config
    os.environ["GEMINI_API_KEY"] = Config.GEMINI_API_KEY
    os.environ["GOOGLE_API_KEY"] = Config.GEMINI_API_KEY
except Exception as e:
    print(f"Failed to load config: {e}")

models_to_test = [
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-flash-latest",
    "google/gemini-1.5-flash",
    "models/gemini-1.5-flash",
    "gemini-1.5-flash",
]

for model in models_to_test:
    try:
        print(f"\n--- Testing {model} ---")
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=5,
        )
        print(f"SUCCESS with {model}!")
    except Exception as e:
        print(f"FAILED with {model}: {e}")
