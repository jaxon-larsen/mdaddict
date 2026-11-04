"""Occurrence identity and source-block ownership survive extraction roundtrips."""
from dataclasses import asdict

import pytest

from mdaddict.strategy import AssetRecord, ExtractResult, SourceBlock, SourceLocator


def test_asset_identity_is_per_occurrence_and_independent_of_description():
    source = SourceLocator('slide', 1, 'shape:2')
    asset = AssetRecord.create(source, (0, 0, 1, 1), 'a' * 64, 'Diagram', ['b'])
    renamed = AssetRecord.create(source, (0., 0., 1., 1.), 'a' * 64, 'Updated description', ['b'])
    other = AssetRecord.create(SourceLocator('slide', 2, 'shape:2'), (0, 0, 1, 1), 'a' * 64, 'Diagram', ['b'])
    assert asset.asset_id == renamed.asset_id != other.asset_id
    assert len(asset.asset_id) == 28
    assert AssetRecord(**asdict(asset)) == asset


@pytest.mark.parametrize('crop', [(0, 0, 0, 1), (-.1, 0, 1, 1), (0, 0, float('nan'), 1)])
def test_invalid_visible_bounds_are_rejected(crop):
    with pytest.raises(ValueError):
        AssetRecord.create(SourceLocator('page', 1), crop, 'a' * 64, 'Diagram', ['b'])


def test_extraction_rejects_asset_owned_by_unknown_block():
    source = SourceLocator('page', 1)
    asset = AssetRecord.create(source, (0, 0, 1, 1), 'a' * 64, 'Diagram', ['missing'])
    with pytest.raises(ValueError, match='unknown source blocks'):
        ExtractResult('a' * 64, 'Text', 'test.pdf', 'control',
            blocks=[SourceBlock('b', 'paragraph', source, 0, 4)], assets=[asset])
