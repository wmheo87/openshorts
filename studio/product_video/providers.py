"""Capability-based boundary; unimplemented APIs cannot be selected or fall back."""
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Capabilities:
    image_generation: bool = False
    image_to_video: bool = False
    avatar: bool = False
    lipsync: bool = False
    approved_media_composition: bool = False


class VideoProvider(ABC):
    id: str
    capabilities: Capabilities

    @abstractmethod
    def render(self, script, config, output_dir, log):
        """One selected provider only. Never select a fallback here."""


class ProductVideoProvider(VideoProvider):
    id = 'ffmpeg-product'
    capabilities = Capabilities(approved_media_composition=True)

    def render(self, script, config, output_dir, log):
        from .render import render_product
        return render_product(script, config, output_dir, log)


class FalActorProvider(VideoProvider):
    id = 'fal-actor'
    capabilities = Capabilities(image_generation=True, image_to_video=True, avatar=True, lipsync=True)

    def render(self, script, config, output_dir, log):
        from saasshorts import generate_full_video
        return config.get('_legacy_render', generate_full_video)(script, config, output_dir, log)


PROVIDERS = {p.id: p for p in (ProductVideoProvider(), FalActorProvider())}


def provider_catalog():
    return [{"id": p.id, "available": True, "capabilities": asdict(p.capabilities),
             "required_keys": ['Gemini'] if p.id == 'ffmpeg-product' else ['fal.ai', 'selected TTS provider'],
             "cost": 'FFmpeg local compute + Gemini script/TTS (pricing unverified)' if p.id == 'ffmpeg-product' else 'fal.ai assets/lipsync + selected TTS; estimates only'}
            for p in PROVIDERS.values()] + [
        {"id": name, "available": False, "capabilities": None,
         "reason": 'Official API contract, account access, pricing and feature support not verified; not implemented'}
        for name in ('kling-official', 'ltx-official')]
