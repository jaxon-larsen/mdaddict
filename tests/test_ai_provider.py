"""A custom provider needs no SDK and cannot bypass repair/cache checks."""
import json

import pytest

from mdaddict import AIResponse, ExtractOptions, ProviderError, extract
from mdaddict.fidelity import repair_regions
from mdaddict.fidelity_geometry import Region
from mdaddict.vision_runtime import BudgetExhausted, VisionRunner


class CustomProvider:
    name, model_id = "developer-adapter", "fixed-model"
    settings = {"temperature": 0}

    def __init__(self, responses, revision="v1"):
        self.responses = iter(responses)
        self.calls = []
        self.cache_identity = {"adapter_revision": revision}

    def call(self, request):
        self.calls.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_custom_provider_transcription_and_verification_cache(tmp_path):
    provider = CustomProvider([
        AIResponse(json.dumps({"patches": [{"id": "r", "markdown": "$A=2$"}]})),
        AIResponse(json.dumps({"decisions": [{"id": "r", "status": "pass"}]})),
    ])
    region = Region("r", "math", (0, 0, 10, 10), 0, 1, "A", True, "uncertain", {})
    runner = VisionRunner(provider, ExtractOptions(max_ai_requests=2), tmp_path)
    assert repair_regions(runner, [region], [b"crop"])[1] is None
    replay = VisionRunner(provider, ExtractOptions(max_ai_requests=0), tmp_path)
    assert repair_regions(replay, [region], [b"crop"])[1] is None
    assert len(provider.calls) == 2 and replay.cache_hits == 2
    changed = CustomProvider([], revision="v2")
    with pytest.raises(BudgetExhausted):
        VisionRunner(changed, ExtractOptions(max_ai_requests=0), tmp_path).request(
            [b"crop"], provider.calls[0].prompt, provider.calls[0].task)


@pytest.mark.parametrize("finish", ["truncated", "blocked", "STOP", ""])
def test_incomplete_or_unnormalized_responses_cannot_be_cached(tmp_path, finish):
    provider = CustomProvider([AIResponse("candidate", finish_reason=finish)])
    with pytest.raises(ProviderError, match="incomplete"):
        VisionRunner(provider, ExtractOptions(), tmp_path).request([b"crop"], "source", "image")
    assert not list(tmp_path.glob("*.json"))


def test_retries_share_the_explicit_request_budget():
    provider = CustomProvider([ProviderError("busy", transient=True)])
    waits = []
    with pytest.raises(BudgetExhausted):
        VisionRunner(provider, ExtractOptions(max_ai_requests=1), sleep=waits.append).request(
            [b"crop"], "source", "image")
    assert len(provider.calls) == 1 and waits == []


@pytest.mark.parametrize("finish", ["complete", "blocked"])
def test_malformed_usage_is_a_provider_error_and_never_cached(tmp_path, finish):
    provider = CustomProvider([AIResponse("text", input_tokens=-1, finish_reason=finish)])
    with pytest.raises(ProviderError, match="nonnegative"):
        VisionRunner(provider, ExtractOptions(), tmp_path).request([b"crop"], "source", "image")
    assert not list(tmp_path.glob("*.json"))


def test_standalone_image_uses_explicit_custom_provider(tmp_path):
    image = pytest.importorskip("PIL.Image")
    path = tmp_path / "scan.png"
    image.new("RGB", (30, 30), "white").save(path)
    provider = CustomProvider([AIResponse("Source words")])
    result = extract(path, ai_provider=provider, options=ExtractOptions(max_ai_requests=1))
    assert "Source words" in result.markdown
    assert result.usage["requests"] == 1
    assert result.review_status == "needs_review"
    assert len(provider.calls) == 1


def test_adapter_identity_is_required_before_conversion(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Source", encoding="utf-8")
    provider = CustomProvider([])
    provider.cache_identity = {}
    with pytest.raises(ValueError, match="cache_identity"):
        extract(source, ai_provider=provider)


def test_custom_provider_repairs_office_pictures_without_vendor_name_checks(tmp_path):
    pptx = pytest.importorskip("pptx")
    image = pytest.importorskip("PIL.Image")
    from io import BytesIO
    picture = BytesIO()
    image.new("RGB", (40, 40), "white").save(picture, format="PNG")
    picture.seek(0)
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_picture(picture, 100, 100)
    source = tmp_path / "pictures.pptx"
    presentation.save(source)
    provider = CustomProvider([
        AIResponse(json.dumps({"patches": [{"id": "office-image", "markdown": "Image labels"}]})),
        AIResponse(json.dumps({"decisions": [{"id": "office-image", "status": "pass"}]})),
    ])
    result = extract(source, ai_provider=provider, options=ExtractOptions(ocr="off", max_ai_requests=2))
    assert len(provider.calls) == 2 and "Image labels" in result.markdown
    assert result.blocks[0].method == "ai"
    assert result.review_status == "needs_review"
