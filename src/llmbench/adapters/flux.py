"""Black Forest Labs (Flux) adapter for image generation via api.bfl.ml.

Implements asynchronous polling to submit requests and wait for completion.
"""

from __future__ import annotations

import asyncio

import httpx

from ..config import env
from ..schema import Capability, ModelSpec
from .base import Adapter, ImageResult, StreamedGeneration

_BASE_URL = "https://api.bfl.ml/v1"


class FluxAdapter(Adapter):
    capabilities = {Capability.IMAGE_GEN}

    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        self.api_key = env("BFL_API_KEY")
        if not self.api_key:
            raise RuntimeError("BFL_API_KEY is not set")
        self._headers = {
            "x-key": self.api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }

    async def stream_generate(self, *args, **kwargs) -> StreamedGeneration:
        raise NotImplementedError("Flux models do not support text generation")

    async def generate_image(self, prompt: str, **kwargs) -> ImageResult:
        # e.g., model "flux-pro-1.1" -> POST https://api.bfl.ml/v1/flux-pro-1.1
        url = f"{_BASE_URL}/{self.spec.model}"
        
        # Parse common dimensions, falling back to 1024x768 if not provided
        size = kwargs.get("size", "1024x768")
        width, height = (int(x) for x in size.split("x", 1)) if "x" in size else (1024, 768)

        body = {
            "prompt": prompt,
            "width": width,
            "height": height,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            # 1. Submit request
            resp = await client.post(url, headers=self._headers, json=body)
            resp.raise_for_status()
            task_id = resp.json().get("id")
            if not task_id:
                raise RuntimeError(f"Failed to obtain task ID from BFL API: {resp.text}")

            # 2. Poll for completion
            poll_url = f"{_BASE_URL}/get_result?id={task_id}"
            while True:
                await asyncio.sleep(1.0)
                poll_resp = await client.get(poll_url, headers=self._headers)
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
                
                status = poll_data.get("status")
                if status == "Ready":
                    sample_url = poll_data.get("result", {}).get("sample")
                    if not sample_url:
                        raise RuntimeError(f"Task Ready but missing sample URL: {poll_data}")
                    
                    # 3. Download generated image
                    img_resp = await client.get(sample_url)
                    img_resp.raise_for_status()
                    return ImageResult(
                        images=[img_resp.content],
                        width=width,
                        height=height,
                    )
                elif status in {"Error", "Failed", "Timeout", "Canceled"}:
                    raise RuntimeError(f"BFL image generation failed: {status} - {poll_data}")
