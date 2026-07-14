"""Manual connectivity check for the configured local model."""

import json

from src.model_client import ModelClient


if __name__ == "__main__":
    result = ModelClient().test_connect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
