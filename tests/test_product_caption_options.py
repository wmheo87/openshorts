"""Unit coverage for product-only ASS styling; no TTS charge or FFmpeg needed."""
from pathlib import Path

import pytest
from studio.product_video.captions import style_product_captions
from studio.product_video.api import ProductRequest, Scene
import uuid


ASS = """[Script Info]
Title: test
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTok,Noto Sans CJK KR,76,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,TikTok,,0,0,0,,정말 편리한 멀티탭
"""


@pytest.mark.parametrize("position,alignment,margin", [
    ("top", "8", "155"),
    ("center", "5", "0"),
    ("bottom", "2", "240"),
])
@pytest.mark.parametrize("style", ["outline", "highlight", "box"])
def test_caption_position_and_style(tmp_path, position, alignment, margin, style):
    path = tmp_path / "captions.ass"
    path.write_text(ASS, encoding="utf-8")
    result = style_product_captions(path, position, style)
    text = path.read_text(encoding="utf-8")
    style_row = next(line for line in text.splitlines() if line.startswith("Style: TikTok,"))
    fields = style_row.removeprefix("Style: ").split(",")
    assert len(fields) == 23
    assert fields[18] == alignment and fields[21] == margin
    assert result["position"] == position and result["style"] == style
    assert "0:00:00.00,0:00:02.00" in text
    if style == "highlight":
        assert r"{\\c&H0000FFFF&}" in text
        assert r"{\\c&H00FFFFFF&}" in text
    elif style == "box":
        assert fields[15] == "3" and fields[6] == "&H90000000"
    else:
        assert fields[15] == "1" and r"{\\c&H0000FFFF&}" not in text


def test_invalid_subtitle_settings_rejected(tmp_path):
    from pydantic import ValidationError
    base = {"request_id": str(uuid.uuid4()), "scenes": [{"asset_id": str(uuid.uuid4())}]}
    assert ProductRequest(**base).subtitle_position == "bottom"
    assert ProductRequest(**base).subtitle_style == "outline"
    with pytest.raises(ValidationError):
        ProductRequest(**base, subtitle_position="outside")
    with pytest.raises(ValidationError):
        ProductRequest(**base, subtitle_style="../../bad.ass")
    p = tmp_path / "test.ass"
    p.write_text(ASS, encoding="utf-8")
    with pytest.raises(ValueError):
        style_product_captions(p, "random", "outline")
