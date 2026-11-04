"""Offline-first file conversion. AI requires an explicitly supplied adapter."""
from .extract import extract, to_markdown
from .ingestion import ingest
from .capabilities import Capability, capabilities, capability_for
from .strategy import (
    AssetRecord, ExtractOptions, ExtractResult, ExtractionIssue, SourceBlock, SourceLocator,
    load_extract, write_extract,
)
from .dependencies import MissingDependencyError
from .ai import AIProvider, AIRequest, AIResponse, ProviderError, MediaAttachment, TranscriptSegment

__version__ = "0.1.0"
__all__ = [
    "AssetRecord", "extract", "to_markdown", "ExtractOptions", "ExtractResult", "ExtractionIssue",
    "SourceBlock", "SourceLocator", "load_extract", "write_extract", "MissingDependencyError",
    "AIProvider", "AIRequest", "AIResponse", "ProviderError", "MediaAttachment", "TranscriptSegment",
    "ingest", "Capability", "capabilities", "capability_for",
]
