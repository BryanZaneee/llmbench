"""Google Gemini adapter via raw httpx.

Supports text generation via streamGenerateContent and image generation via predict (Imagen 3).
"""

from __future__ import annotations

import base64
import json
import time

import httpx

from ..config import env
from ..schema import Capability, ModelSpec, TokenUsage
from .base import Adapter, GenerationEvent, ImageResult, StreamedGeneration

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter(Adapter):
    capabilities = {Capability.TEXT, Capability.IMAGE_GEN}

    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        self.api_key = env("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._headers = {
            "x-goog-api-key": self.api_key,
            "content-type": "application/json",
        }

    async def stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> StreamedGeneration:
        url = f"{_BASE_URL}/{self.spec.model}:streamGenerateContent?alt=sse"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                "topP": top_p,
            },
        }

        events: list[GenerationEvent] = []
        text_parts: list[str] = []
        usage = TokenUsage()
        stop_reason: str | None = None

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, headers=self._headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                        
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Extract usage if present
                    meta = chunk.get("usageMetadata")
                    if meta:
                        usage = TokenUsage(
                            input_tokens=int(meta.get("promptTokenCount", usage.input_tokens)),
                            output_tokens=int(meta.get("candidatesTokenCount", usage.output_tokens)),
                            cached_input_tokens=int(meta.get("cachedContentTokenCount", usage.cached_input_tokens)),
                        )

                    candidates = chunk.get("candidates", [])
                    if not candidates:
                        continue
                        
                    candidate = candidates[0]
                    if "finishReason" in candidate:
                        stop_reason = candidate["finishReason"]

                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            text = part["text"]
                            text_parts.append(text)
                            events.append(GenerationEvent(text=text, timestamp=time.perf_counter()))

        return StreamedGeneration(
            text="".join(text_parts),
            events=events,
            usage=usage,
            stop_reason=stop_reason,
        )

    async def generate_image(self, prompt: str, **kwargs) -> ImageResult:
        # Google's image generation endpoint (Imagen 3) typically uses :predict
        url = f"{_BASE_URL}/{self.spec.model}:predict"
        n = kwargs.get("n", 1)
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": n},
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=self._headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        predictions = data.get("predictions", [])
        images: list[bytes] = []
        for pred in predictions:
            if "bytesBase64Encoded" in pred:
                images.append(base64.b64decode(pred["bytesBase64Encoded"]))

        return ImageResult(images=images, width=0, height=0)
