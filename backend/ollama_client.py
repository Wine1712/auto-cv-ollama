# backend/ollama_client.py
from __future__ import annotations

from typing import Optional
import requests
from fastapi import HTTPException


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def ollama_generate(model: str, prompt: str, *, timeout: int = 240) -> str:
    """
    Requires: `ollama serve` running locally.
    """
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama request timed out")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Ollama connection failed: {e}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Ollama error: {r.text}")

    data = r.json()
    return (data.get("response") or "").strip()