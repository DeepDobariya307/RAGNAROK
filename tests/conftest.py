import os
import sys
from pathlib import Path

# Tests run fully offline: no OpenAI or Pinecone calls are made.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")
