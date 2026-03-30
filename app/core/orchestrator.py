import asyncio
import os
from typing import Any, Dict, Optional
from urllib.parse import quote
import httpx


class Orchestrator:
    def __init__(self, ollama_url: str = None, model: str = "llama3:8b"):
        self.ollama_url = ollama_url or os.getenv(
            "OLLAMA_URL", "http://localhost:11434"
        )
        self.model = model

    async def call_ollama(self, prompt: str) -> Dict[str, Any]:
        """
        Call Ollama using one of the supported endpoints.

        We try multiple endpoints because some Ollama installs expose only the native
        endpoints (`/api/chat`, `/api/generate`) and not the OpenAI-compatible ones
        (`/v1/chat/completions`).
        """
        candidates = [
            # OpenAI-compatible endpoint (if enabled by your Ollama version/settings)
            (
                f"{self.ollama_url}/v1/chat/completions",
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            ),
            # Native chat endpoint
            (
                f"{self.ollama_url}/api/chat",
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            ),
            # Native generate endpoint
            (
                f"{self.ollama_url}/api/generate",
                {"model": self.model, "prompt": prompt, "stream": False},
            ),
        ]

        last_err: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            for url, payload in candidates:
                try:
                    print(
                        f"Calling Ollama at {url} with payload keys: {list(payload.keys())}"
                    )
                    res = await client.post(url, json=payload)
                    res.raise_for_status()
                    return res.json()
                except Exception as err:
                    last_err = err
                    print(f"HTTP error calling {url}: {err}")

        raise RuntimeError(
            "No working Ollama endpoint found. Tried: "
            + ", ".join([c[0] for c in candidates])
            + f". Last error: {last_err}"
        )

    def _extract_generated_text(self, ollama_response: Dict[str, Any]) -> Optional[str]:
        generated: Optional[str] = None

        if isinstance(ollama_response, dict):
            # Ollama native: /api/generate returns {"response": "...", ...}
            if ollama_response.get("response") and isinstance(
                ollama_response.get("response"), str
            ):
                generated = ollama_response.get("response")

            # Ollama native: /api/chat returns {"message": {"role": "...", "content": "..."}, ...}
            if generated is None and isinstance(ollama_response.get("message"), dict):
                msg = ollama_response.get("message")
                if isinstance(msg, dict) and msg.get("content"):
                    generated = msg.get("content")

            if ollama_response.get("output"):
                generated = ollama_response.get("output")

            choices = ollama_response.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict) and message.get("content"):
                        generated = message.get("content")
                    elif first.get("text"):
                        generated = first.get("text")
                    elif first.get("output"):
                        generated = first.get("output")

            if generated is None and ollama_response.get("result"):
                generated = ollama_response.get("result")

        return generated

    async def generate_text(self, prompt: str) -> str:
        """
        Generate a plain text response from Ollama.

        We keep this small and deterministic because the calling code relies on it.
        """
        ollama_response = await self.call_ollama(prompt)
        if isinstance(ollama_response, dict):
            generated = self._extract_generated_text(ollama_response)
            if generated is not None:
                return str(generated)
        return str(ollama_response)

    async def orchestrate_text_prompt(self, query, *args, **kwargs):
        # Backward-compatible method for the existing endpoint.
        text = query.query if hasattr(query, "query") else str(query)
        generated_text = await self.generate_text(text)
        return {
            "query": text,
            "generated_text": generated_text,
        }
