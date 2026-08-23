"""Download the embedding model into backend/models_cache at build time.

Run during the Render build so the web service never has to reach the
Hugging Face Hub at startup.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model2vec import StaticModel  # noqa: E402

from services.rag import EMBED_MODEL_DIR, EMBED_MODEL_ID  # noqa: E402

if __name__ == "__main__":
    if os.path.isdir(EMBED_MODEL_DIR):
        print(f"embedder already at {EMBED_MODEL_DIR}")
    else:
        StaticModel.from_pretrained(EMBED_MODEL_ID).save_pretrained(EMBED_MODEL_DIR)
        print(f"saved {EMBED_MODEL_ID} to {EMBED_MODEL_DIR}")
