import asyncio
import os
from typing import Any, Dict, Optional
from urllib.parse import quote
import httpx


class Orchestrator:
    def __init__(
        self,
        provider: str = None,
        ollama_url: str = None,
        ollama_model: str = "llama3:8b",
        openai_model: str = "gpt-3.5-turbo",
        gemini_model: str = "gemini-1.5-flash",
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3:8b")
        self.model = self.ollama_model  # backward compatibility for existing code paths
        self.openai_model = openai_model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

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
                    "model": self.ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            ),
            # Native chat endpoint
            (
                f"{self.ollama_url}/api/chat",
                {
                    "model": self.ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            ),
            # Native generate endpoint
            (
                f"{self.ollama_url}/api/generate",
                {"model": self.ollama_model, "prompt": prompt, "stream": False},
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

    async def call_openai(self, prompt: str) -> Dict[str, Any]:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        payload = {
            "model": self.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            res.raise_for_status()
            return res.json()

    async def call_gemini(self, prompt: str) -> Dict[str, Any]:
        gemini_key = os.getenv("GEMINI_API_KEY")
        model_id = self.gemini_model
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        headers = {
            "Content-Type": "application/json",
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={gemini_key}"

        last_err: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                print(f"Calling Gemini at {url}")
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                return res.json()
            except Exception as err:
                last_err = err
                print(f"HTTP error calling {url}: {err}")

        raise RuntimeError(
            "No working Gemini endpoint found. Tried: "
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

            # Gemini response structure: {"candidates": [{"output": "..."}]} or {"candidates": [{"content": [{"text": "..."}]}]}
            candidates = ollama_response.get("candidates")
            if generated is None and isinstance(candidates, list) and candidates:
                first_candidate = candidates[0]
                if isinstance(first_candidate, dict):
                    if first_candidate.get("output"):
                        generated = first_candidate.get("output")
                    elif first_candidate.get("content"):
                        content = first_candidate.get("content")
                        if isinstance(content, list) and content:
                            first_content = content[0]
                            if isinstance(first_content, dict) and first_content.get("text"):
                                generated = first_content.get("text")

            if generated is None and ollama_response.get("result"):
                generated = ollama_response.get("result")

        return generated

    async def generate_text(self, prompt: str) -> str:
        """
        Generate a plain text response from the configured provider.

        Supports `ollama` (default) and `openai` (via OPENAI_API_KEY).
        """
        if self.provider == "openai":
            response = await self.call_openai(prompt)
        elif self.provider == "ollama":
            response = await self.call_ollama(prompt)
        elif self.provider == "gemini":
            response = await self.call_gemini(prompt)
        else:
            raise RuntimeError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. Use 'ollama', 'openai', or 'gemini'."
            )

        if isinstance(response, dict):
            generated = self._extract_generated_text(response)
            if generated is not None:
                return str(generated)
        return str(response)

    async def handle_query(self, user_query: str) -> str:
        """High-level orchestration method: validates and handles company service logic."""
        from app.services.company_chat_service import CompanyChatService

        service = CompanyChatService()
        return await service.handle(user_query)

    async def orchestrate_text_prompt(self, query, *args, **kwargs):
        # Backward-compatible method for the existing endpoint.
        text = query.query if hasattr(query, "query") else str(query)
        generated_text = await self.generate_text(text)
        return {
            "query": text,
            "generated_text": generated_text,
        }
