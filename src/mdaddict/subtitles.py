"""Maintained subtitle parser with original cue times and source spans."""
from .dependencies import MissingDependencyError
from .strategy import ExtractResult, ExtractionIssue, SourceBlock, SourceLocator, normalize, sha256_file


def extract_subtitles(path, options):
    try:
        import pysubs2
    except ImportError as exc:
        raise MissingDependencyError("Install mdaddict[captions] to read SRT/WebVTT files.") from exc
    cues = pysubs2.load(str(path), encoding=options.encoding)
    chunks, blocks, segments = [], [], []
    offset = 0
    for index, cue in enumerate(cues, 1):
        if index > options.max_cells:
            raise ValueError("Subtitle cue count exceeds max_cells")
        if cue.start < 0 or cue.end < cue.start:
            raise ValueError("Invalid subtitle cue interval")
        start, end = cue.start / 1000, cue.end / 1000
        chunk = normalize(f"[{start:g}–{end:g}s] {cue.plaintext}")
        chunks.append(chunk)
        blocks.append(SourceBlock(f"cue:{index}", "transcript", SourceLocator("recording", 1, f"seconds:{start:g}-{end:g}"), offset, offset + len(chunk)))
        segments.append({"text": cue.plaintext, "start_seconds": start, "end_seconds": end})
        offset += len(chunk)
    issues = [ExtractionIssue("subtitle_visual_unprocessed", "Subtitle text and times were read; recording audio and visuals were not verified.", severity="review")]
    if not chunks or not any(cue.plaintext.strip() for cue in cues):
        issues.append(ExtractionIssue("subtitle_content_empty", "The subtitle file has no readable cue text.", severity="unresolved"))
    result = ExtractResult(sha256_file(path), "".join(chunks), path.name, "pysubs2",
        blocks=blocks, issues=issues, metadata={"captions": {"segments": segments}}, usage={"requests": 0})
    result.refresh_status()
    return result
