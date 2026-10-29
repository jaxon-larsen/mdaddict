"""Explicit provider-based speech transcription; video visuals are not processed."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from .ai import AIRequest, ProviderError, validate_provider, validate_response
from .strategy import ExtractOptions, ExtractResult, ExtractionIssue, SourceBlock, SourceLocator, normalize

AUDIO_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
               ".ogg": "audio/ogg", ".flac": "audio/flac", ".aac": "audio/aac",
               ".opus": "audio/ogg", ".oga": "audio/ogg", ".wma": "audio/x-ms-wma", ".aiff": "audio/aiff", ".aif": "audio/aiff"}
from .capabilities import VIDEO_TYPES


def _timestamp(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ProviderError("Transcript timestamps must be finite nonnegative seconds")
    return float(value)


def _video_audio(path: Path, options: ExtractOptions) -> bytes:
    binary = shutil.which("ffmpeg")
    if binary is None:
        raise RuntimeError("Video speech transcription requires ffmpeg on PATH; no download was attempted")
    maximum = options.max_mb * 1024 * 1024
    with tempfile.TemporaryDirectory(prefix="mdaddict-audio-") as directory:
        destination = Path(directory) / "speech.wav"
        run = subprocess.run([binary, "-nostdin", "-v", "error", "-i", str(path),
                              "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                              "-fs", str(maximum + 1), str(destination)],
                             capture_output=True, timeout=options.timeout)
        if run.returncode or not destination.is_file():
            raise RuntimeError("ffmpeg could not extract a speech audio track")
        if destination.stat().st_size >= maximum:
            raise ValueError("Decoded video audio exceeds max_mb; truncated audio was not transcribed")
        return destination.read_bytes()


def transcribe_media(path: Path, *, provider, options: ExtractOptions) -> ExtractResult:
    """One bounded input and one explicit call; adapter owns its call timeout.

    The attachment contains original audio bytes, or ffmpeg-decoded audio for a
    video. No frames are sent, and a transcript never certifies visual content.
    """
    from .ai import MediaAttachment

    started = time.perf_counter()
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in AUDIO_TYPES and suffix not in VIDEO_TYPES:
        raise ValueError(f"Unsupported media type: {suffix}")
    if not path.is_file():
        raise FileNotFoundError(path)
    maximum = options.max_mb * 1024 * 1024
    if path.stat().st_size > maximum:
        raise ValueError("Media input exceeds max_mb")
    if provider is None:
        raise ValueError("Speech transcription requires an explicitly supplied audio provider")
    identity = validate_provider(provider)
    modalities = getattr(provider, "modalities", ("vision",))
    if isinstance(modalities, str) or "audio" not in modalities:
        raise ValueError("The explicit provider must advertise the 'audio' modality")
    if options.max_ai_requests is not None and options.max_ai_requests < 1:
        raise ValueError("Speech transcription requires one permitted model request")
    original = path.read_bytes()
    if not original or len(original) > maximum:
        raise ValueError("Media input is empty or exceeds max_mb")
    is_video = suffix in VIDEO_TYPES
    data = _video_audio(path, options) if is_video else original
    response = provider.call(AIRequest(
        images=[], media=[MediaAttachment(data=data, mime_type="audio/wav" if is_video else AUDIO_TYPES[suffix],
                                         filename="speech.wav" if is_video else path.name)],
        prompt="Transcribe the supplied speech faithfully. Preserve qualifications and numbers; do not summarize or infer visuals. Provide timed segments when available.",
        system="You transcribe audio. Mark inaudible or uncertain passages explicitly; never invent missing speech.",
        max_tokens=options.max_tokens, task="transcribe_audio"))
    validate_response(response)
    chunks, blocks, segments = [], [], []
    offset = 0
    previous_start = -1.0
    for index, segment in enumerate(getattr(response, "segments", []), 1):
        if index > options.max_cells:
            raise ProviderError("Transcript segment count exceeds max_cells")
        begin, end = _timestamp(segment.start_seconds), _timestamp(segment.end_seconds)
        if end < begin or begin < previous_start:
            raise ProviderError("Transcript intervals must have end >= start and ordered starts")
        if not isinstance(segment.text, str) or not segment.text.strip():
            raise ProviderError("Transcript segments must contain nonempty text")
        previous_start = begin
        chunk = normalize(f"[{begin:g}–{end:g}s] {segment.text}")
        blocks.append(SourceBlock(f"segment:{index}", "transcript", SourceLocator("recording", 1, f"seconds:{begin:g}-{end:g}"),
                                  offset, offset + len(chunk), "ai"))
        chunks.append(chunk)
        segments.append({"text": segment.text, "start_seconds": begin, "end_seconds": end})
        offset += len(chunk)
    if not chunks:
        chunks = [normalize(response.text)]
        blocks = [SourceBlock("recording:1", "transcript", SourceLocator("recording", 1, "untimed"), 0, len(chunks[0]), "ai")]
    issues = [ExtractionIssue("media_transcription_review", "Speech transcript is unverified and requires source review",
                              SourceLocator("recording", 1), [b.id for b in blocks], "review")]
    if not segments:
        issues.append(ExtractionIssue("media_timestamps_unavailable", "Provider supplied no timed segments; no timestamps were inferred",
                                      SourceLocator("recording", 1), [blocks[0].id], "review"))
    if is_video:
        issues.append(ExtractionIssue("video_visual_unprocessed", "Only audio was transcribed; video frames, on-screen text, and visual relationships were not processed",
                                      SourceLocator("recording", 1), [b.id for b in blocks], "unresolved"))
    result = ExtractResult(hashlib.sha256(original).hexdigest(), "".join(chunks), path.name,
        "media:explicit-audio-provider", blocks=blocks, issues=issues,
        usage={"requests": 1, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
               "thinking_tokens": response.thinking_tokens},
        metadata={"provider_settings": identity, "media": {"scope": "speech-only", "segments": segments,
                  "original_sha256": hashlib.sha256(original).hexdigest(), "attachment_sha256": hashlib.sha256(data).hexdigest(),
                  "audio_extracted_from_video": is_video, "response_text": response.text}},
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2))
    result.refresh_status()
    return result
