"""Embeddings via OpenAI API (no local torch needed — works on Python 3.14).

To switch to a local multilingual model later (bge-m3 / multilingual-e5),
replace embed_texts() with a sentence-transformers call and update EMBED_DIM.
"""
from openai import OpenAI
import config

_client = OpenAI(api_key=config.OPENAI_API_KEY)


def embed_texts(texts):
    """texts: list[str] -> list[list[float]]"""
    resp = _client.embeddings.create(model=config.EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def embed_one(text):
    return embed_texts([text])[0]
