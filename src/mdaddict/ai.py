"""Opt-in, synchronous model-call protocol; this module performs no network IO."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Mapping
import json
import math


@dataclass(frozen=True)
class MediaAttachment:
    data: bytes
    mime_type: str
    filename: str


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class VisionRequest:
    images: list[bytes]
    prompt: str
    system: str
    max_tokens: int
    task: str = "transcribe"
    media: list[MediaAttachment] = field(default_factory=list)


@dataclass(frozen=True)
class VisionResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    finish_reason: str = "complete"
    model_id: str = ""
    provider: str = ""
    segments: list[TranscriptSegment] = field(default_factory=list)


class ProviderError(RuntimeError, ValueError):
    def __init__(self, message: str, *, transient: bool = False,
                 configuration: bool = False, response: VisionResponse | None = None,
                 retry_after: float | None = None):
        super().__init__(message)
        self.transient = transient
        self.configuration = configuration
        self.response = response
        self.retry_after = retry_after

class AIProvider(Protocol):
    """Identity must describe model/configuration/revision and contain no credentials."""
    name: str
    model_id: str
    settings: Mapping[str, object]

    @property
    def cache_identity(self) -> Mapping[str, object]: ...

    def call(self, request: VisionRequest) -> VisionResponse: ...


AIRequest = VisionRequest
AIResponse = VisionResponse


def provider_modalities(provider) -> frozenset[str]:
    """Legacy adapters are image-only; audio/video require explicit capability."""
    values = getattr(provider, "modalities", ("vision",))
    if isinstance(values, str) or not isinstance(values, (list, tuple, set, frozenset)):
        raise TypeError("provider.modalities must be a collection of modality names")
    if any(not isinstance(value, str) or value not in {"vision", "audio", "video"} for value in values):
        raise ValueError("Unknown provider modality")
    return frozenset(values)


def validate_provider(provider: AIProvider) -> dict:
    """Require an explicit reproducible identity before any call or cache read."""
    if not callable(getattr(provider, "call", None)):
        raise TypeError("ai_provider must implement call(AIRequest) -> AIResponse")
    if not isinstance(getattr(provider, "name", None), str) or not provider.name:
        raise ValueError("ai_provider.name must be nonempty")
    if not isinstance(getattr(provider, "model_id", None), str) or not provider.model_id:
        raise ValueError("ai_provider.model_id must be nonempty")
    identity = getattr(provider, "cache_identity", None)
    if not isinstance(identity, Mapping) or not identity:
        raise ValueError("ai_provider.cache_identity must describe model, settings and adapter revision")
    settings = getattr(provider, "settings", None)
    if not isinstance(settings, Mapping):
        raise ValueError("ai_provider.settings must be a mapping without credentials")
    # Copy the identity so later mutation cannot change the already-computed key.
    return json.loads(json.dumps({"name": provider.name, "model_id": provider.model_id,
                                  "settings": dict(settings), "adapter": dict(identity),
                                  "modalities": sorted(provider_modalities(provider))}, allow_nan=False))


def validate_response(response: AIResponse) -> None:
    if not isinstance(response, AIResponse):
        raise ProviderError("Provider must return AIResponse")
    for value in (response.input_tokens, response.output_tokens, response.thinking_tokens):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ProviderError("AI response usage must be nonnegative integers")
    if response.finish_reason != "complete" or not isinstance(response.text, str) or not response.text.strip():
        raise ProviderError("AI response is incomplete, blocked, or empty; not cached", response=response)
    if not isinstance(response.segments, list):
        raise ProviderError("Transcript segments must be a list")
    previous = 0.0
    for segment in response.segments:
        if (not isinstance(segment, TranscriptSegment) or not isinstance(segment.text, str) or not segment.text.strip()
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in (segment.start_seconds, segment.end_seconds))
            or not 0 <= segment.start_seconds <= segment.end_seconds or segment.start_seconds < previous):
            raise ProviderError("Invalid transcript segment timing/text")
        previous = segment.start_seconds
