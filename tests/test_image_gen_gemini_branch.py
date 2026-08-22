"""Guards the model-id-based split in GeminiAdapter.generate_image.

`gemini-*-image*` models go through :generateContent (Nano Banana 2 et al);
`imagen-*` models keep the original :predict path. Both must keep working.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from llmbench.adapters.gemini import GeminiAdapter
from llmbench.schema import ModelSpec

# 1x1 transparent PNG, same bytes as test_image_gen.py uses.
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
    b"\xc0\xf0\x1f\x00\x05\x00\x01\xff\xa1\xf9\x97\xd2\x00\x00\x00\x00IEND\xaeB`\x82"
)
_PNG_B64 = base64.b64encode(_PNG_BYTES).decode("ascii")


def _install_mock_transport(monkeypatch, handler):
    """Make every httpx.AsyncClient(...) inside the adapter route through MockTransport."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_gemini_image_uses_generate_content_for_nano_banana(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"inline_data": {"mime_type": "image/png", "data": _PNG_B64}}
                            ],
                        }
                    }
                ]
            },
        )

    _install_mock_transport(monkeypatch, handler)

    spec = ModelSpec(
        provider="gemini",
        adapter="gemini",
        model="gemini-3.1-flash-image-preview",
        benchmarks=["image_gen"],
    )
    result = await GeminiAdapter(spec).generate_image("a cat")

    assert ":generateContent" in captured["url"]
    assert captured["body"]["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
    assert len(result.images) == 1
    assert result.images[0] == _PNG_BYTES


@pytest.mark.asyncio
async def test_gemini_image_keeps_predict_for_imagen(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={"predictions": [{"bytesBase64Encoded": _PNG_B64}]},
        )

    _install_mock_transport(monkeypatch, handler)

    spec = ModelSpec(
        provider="gemini",
        adapter="gemini",
        model="imagen-3.0-generate-002",
        benchmarks=["image_gen"],
    )
    result = await GeminiAdapter(spec).generate_image("a cat")

    assert ":predict" in captured["url"]
    assert len(result.images) == 1
    assert result.images[0] == _PNG_BYTES
