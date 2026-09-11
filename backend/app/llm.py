"""LLM client abstraction.

Supports:
  * Google Gemini (REST API via httpx — no SDK required)
  * OpenAI-compatible chat completions
  * mock mode — deterministic, offline responses so the whole
    platform can run end-to-end without API keys

The provider is chosen by LLM_PROVIDER (auto | gemini | openai | mock).
`auto` picks the provider matching whichever API key is set.
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings


class LLMError(RuntimeError):
    pass


def _resolve_provider() -> str:
    if settings.llm_provider in ("gemini", "openai", "mock"):
        return settings.llm_provider
    if settings.gemini_api_key:
        return "gemini"
    if settings.openai_api_key:
        return "openai"
    return "mock"


import asyncio
import logging
import random

logger = logging.getLogger(__name__)

GEMINI_FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


class LLMClient:
    """Thin async wrapper around Gemini / OpenAI / mock completions with retries and fallbacks."""

    def __init__(self) -> None:
        self._provider = _resolve_provider()

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def is_mock(self) -> bool:
        return self._provider == "mock"

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        *,
        json_mode: bool = False,
        temperature: float = 0.6,
        max_tokens: int = 4000,
    ) -> str:
        """Run a completion and return the raw text."""
        if self._provider == "gemini":
            text = await self._gemini(prompt, system, temperature, max_tokens)
        elif self._provider == "openai":
            text = await self._openai(prompt, system, temperature, max_tokens)
        else:  # pragma: no cover - guarded by callers
            raise LLMError("mock provider has no complete()")
        if json_mode and text:
            extracted = extract_json(text)
            if extracted is not None:
                return extracted
        return text

    async def _gemini(self, prompt: str, system: str | None, temperature: float, max_tokens: int) -> str:
        # Build prioritized model list
        models = [settings.gemini_model]
        for fb in GEMINI_FALLBACK_MODELS:
            if fb not in models:
                models.append(fb)

        parts: list[dict] = []
        if system:
            parts.append({"text": system})
        parts.append({"text": prompt})
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        last_error: Exception | None = None
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
                        resp = await client.post(
                            url,
                            params={"key": settings.gemini_api_key},
                            json=body,
                        )
                        if resp.status_code in (429, 500, 502, 503, 504):
                            wait = (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
                            logger.warning(
                                "Gemini model %s returned status %s (attempt %s/%s). Retrying in %.1fs...",
                                model, resp.status_code, attempt, max_attempts, wait
                            )
                            if attempt < max_attempts:
                                await asyncio.sleep(wait)
                                continue
                            # If attempts exhausted for this model, break to fallback model
                            last_error = LLMError(f"Gemini API error {resp.status_code} on {model}: {resp.text[:300]}")
                            break

                        resp.raise_for_status()
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    wait = (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
                    logger.warning(
                        "Gemini model %s network/timeout error (attempt %s/%s): %s. Retrying in %.1fs...",
                        model, attempt, max_attempts, exc, wait
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(wait)
                        continue
                    last_error = LLMError(f"Gemini request failed on {model}: {exc}")
                    break
                except (KeyError, IndexError, TypeError) as exc:
                    raise LLMError(f"Unexpected Gemini response structure: {exc}") from exc
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        # Model not available / deprecated -> immediately try next model in fallback list
                        logger.warning("Gemini model %s not found (404). Falling back to next model...", model)
                        last_error = LLMError(f"Gemini model {model} not found: {exc.response.text[:300]}")
                        break
                    raise LLMError(f"Gemini API error {exc.response.status_code}: {exc.response.text[:500]}") from exc

            logger.info("Attempting fallback from Gemini model %s to next available model...", model)

        if last_error:
            raise last_error
        raise LLMError("Gemini API request failed across all candidate models.")

    async def _openai(self, prompt: str, system: str | None, temperature: float, max_tokens: int) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                        json=body,
                    )
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                        wait = (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < max_attempts:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise LLMError(f"OpenAI request failed: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                raise LLMError(f"OpenAI API error {exc.response.status_code}: {exc.response.text[:500]}") from exc
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"Unexpected OpenAI response: {json.dumps(data)[:500]}") from exc
        raise LLMError("OpenAI request failed after retries.")


# --- JSON helpers --------------------------------------------------------------

def extract_json(text: str) -> str | None:
    """Pull the first top-level JSON object or array out of an LLM response.

    Tolerates markdown fences and surrounding prose. Tracks nested brackets of
    both kinds so an object containing arrays (or vice versa) is returned in
    full instead of just its first nested value.
    """
    if not text:
        return None
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find whichever bracket kind starts first.
    starts = [(text.find(ch), ch) for ch in ("[", "{")]
    starts = [(pos, ch) for pos, ch in starts if pos != -1]
    if not starts:
        return None
    start, open_ch = min(starts)
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in ("[", "{"):
            depth += 1
        elif ch in ("]", "}"):
            depth -= 1
            if depth == 0 and ch == close_ch:
                return text[start : i + 1]
    return None


def parse_json_object(text: str) -> dict | None:
    raw = extract_json(text)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_json_list(text: str) -> list | None:
    raw = extract_json(text)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None