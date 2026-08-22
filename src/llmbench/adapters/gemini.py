"""Google Gemini adapter via raw httpx.

Text generation goes through :streamGenerateContent. Image generation has two
shapes: Imagen models (e.g. imagen-3.0-generate-002) use :predict with an
"instances"/"predictions" schema; Gemini multimodal image models (e.g.
gemini-3.1-flash-image-preview, the "Nano Banana 2" model) use
:generateContent with responseModalities=["TEXT","IMAGE"] and return image
bytes inline on the candidate parts.
"""

from __future__ import annotations

import base64
import json
import time

import httpx

from ..config import require_key
from ..schema import Capability, ModelSpec, TokenUsage
from .base import Adapter, GenerationEvent, ImageResult, StreamedGeneration

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter(Adapter):
    capabilities = {Capability.TEXT, Capability.IMAGE_GEN}

    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        self.api_key = require_key(spec.provider, spec.adapter)
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
        model = self.spec.model
        # Gemini 3.x multimodal image models ride on :generateContent. Imagen
        # (and any future :predict-shaped model) keeps the existing path.
        if model.startswith("gemini-") and "image" in model:
            return await self._generate_image_via_generate_content(prompt)
        return await self._generate_image_via_predict(prompt, n=kwargs.get("n", 1))

    async def _generate_image_via_predict(self, prompt: str, *, n: int) -> ImageResult:
        url = f"{_BASE_URL}/{self.spec.model}:predict"
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": n},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=self._headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        images: list[bytes] = []
        for pred in data.get("predictions", []):
            if "bytesBase64Encoded" in pred:
                images.append(base64.b64decode(pred["bytesBase64Encoded"]))
        return ImageResult(images=images, width=0, height=0)

    async def _generate_image_via_generate_content(self, prompt: str) -> ImageResult:
        url = f"{_BASE_URL}/{self.spec.model}:generateContent"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=self._headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        images: list[bytes] = []
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                # REST returns inline_data; some SDK paths use inlineData.
                inline = part.get("inline_data") or part.get("inlineData")
                if inline and inline.get("data"):
                    images.append(base64.b64decode(inline["data"]))
        return ImageResult(images=images, width=0, height=0)
