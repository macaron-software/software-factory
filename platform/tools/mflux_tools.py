"""
MFlux Tools — Apple Silicon image generation via mflux (FLUX.1 on MLX).
========================================================================
WHY: mflux runs FLUX.1 models locally on Apple Silicon via MLX — no API key,
no cloud cost, fast inference on M-series chips. This tool gates on ARM64 and
gracefully degrades on non-Apple-Silicon hosts so the same agent code works
everywhere (CI, Linux servers) without crashing.

SOURCE: https://github.com/filipstrand/mflux  (MIT)
"""

from __future__ import annotations

import json
import logging
import platform as _platform
from typing import TYPE_CHECKING

from .registry import BaseTool

if TYPE_CHECKING:
    from ..models import AgentInstance

logger = logging.getLogger(__name__)


class MfluxGenerateTool(BaseTool):
    name = "mflux_generate"
    description = (
        "Generate an image from a text prompt using FLUX.1 on Apple Silicon (mflux/MLX). "
        "params: prompt (str, required), model (str, default 'flux-schnell', options: flux-schnell|flux-dev), "
        "steps (int, default 2), width (int, default 512), height (int, default 512), "
        "output_path (str, optional). macOS Apple Silicon only."
    )
    category = "generation"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        import time

        machine = _platform.machine()
        if machine != "arm64":
            return json.dumps(
                {"error": f"mflux requires Apple Silicon (ARM64). Current: {machine}"}
            )

        try:
            import mflux  # noqa: F401 — availability check
        except ImportError:
            return json.dumps(
                {
                    "error": (
                        "mflux not installed. Run: pip install mflux "
                        "(macOS Apple Silicon only)"
                    )
                }
            )

        prompt = params.get("prompt", "")
        if not prompt:
            return json.dumps({"error": "prompt is required"})

        model = params.get("model", "flux-schnell")
        if model not in ("flux-schnell", "flux-dev"):
            model = "flux-schnell"
        steps = int(params.get("steps", 2))
        width = int(params.get("width", 512))
        height = int(params.get("height", 512))

        timestamp = int(time.time())
        output_path = params.get("output_path") or f"output/mflux_{timestamp}.png"

        try:
            from mflux import Flux1, Config

            flux = Flux1.from_alias(alias=model, quantize=4)
            image = flux.generate_image(
                prompt=prompt,
                config=Config(num_inference_steps=steps, width=width, height=height),
            )
            image.save(path=output_path)

            return json.dumps(
                {
                    "path": output_path,
                    "model": model,
                    "steps": steps,
                    "width": width,
                    "height": height,
                    "platform": "Apple Silicon",
                }
            )
        except Exception as exc:
            logger.error("mflux_generate failed: %s", exc)
            return json.dumps({"error": str(exc)})


def register_mflux_tools(registry) -> None:
    registry.register(MfluxGenerateTool())
    logger.debug("MFlux tools registered (1 tool)")
