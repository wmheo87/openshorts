"""Apply safe, user-selected ASS caption layout to product-video subtitles only.

This transforms the existing timed Whisper ASS output. It does not alter timing
or touch actor-style subtitle rendering.
"""
from pathlib import Path
import re

POSITIONS = {"top": (8, 155), "center": (5, 0), "bottom": (2, 240)}
STYLES = {"outline", "highlight", "box"}


def style_product_captions(path, position="bottom", style="outline"):
    if position not in POSITIONS or style not in STYLES:
        raise ValueError("지원하지 않는 자막 위치 또는 스타일입니다.")
    file = Path(path)
    content = file.read_text(encoding="utf-8")
    if "[V4+ Styles]" not in content or "[Events]" not in content:
        raise ValueError("유효한 ASS 자막이 아닙니다.")

    alignment, margin = POSITIONS[position]
    lines = []
    in_styles = False
    in_events = False
    changed_style = False
    dialogue_count = 0
    for line in content.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if stripped.startswith("["):
            in_styles = stripped == "[V4+ Styles]"
            in_events = stripped == "[Events]"
        if in_styles and stripped.startswith("Style: TikTok,"):
            parts = stripped.removeprefix("Style: ").split(",")
            # Standard ASS fields match the generator's style format.
            if len(parts) != 23:
                raise ValueError("ASS 스타일 형식이 예상과 다릅니다.")
            parts[18] = str(alignment)
            parts[21] = str(margin)
            if style == "box":
                parts[15] = "3"             # opaque background box
                parts[16] = "0"             # outline thickness
                parts[17] = "0"             # shadow
                parts[6] = "&H90000000"     # semi-transparent black back colour
            else:
                parts[15] = "1"             # normal outlined text
                parts[16] = "4"
                parts[17] = "0"
            line = "Style: " + ",".join(parts) + "\n"
            changed_style = True
        elif in_events and stripped.startswith("Dialogue: ") and style == "highlight":
            fields = stripped.split(",", 9)
            if len(fields) == 10:
                spoken = fields[9]
                # Highlight the longest Hangul/Latin word within each short
                # Whisper chunk; avoid interpreting ASS override syntax.
                tokens = list(re.finditer(r"[가-힣A-Za-z0-9]{2,}", spoken))
                if tokens:
                    token = max(tokens, key=lambda m: len(m.group(0)))
                    spoken = (spoken[:token.start()] + r"{\\c&H0000FFFF&}" +
                              token.group(0) + r"{\\c&H00FFFFFF&}" +
                              spoken[token.end():])
                    fields[9] = spoken
                    line = ",".join(fields) + "\n"
            dialogue_count += 1
        lines.append(line)

    if not changed_style:
        raise ValueError("TikTok 자막 스타일이 없습니다.")
    file.write_text("".join(lines), encoding="utf-8")
    return {"position": position, "style": style, "highlighted_lines": dialogue_count}
