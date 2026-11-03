"""Rebuild UI-only font: python subset-korean-font.py /path/NotoSansCJK-Regular.ttc.
Requires fonttools (development only); output is redistributed under OFL-1.1.
"""
import sys
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

font = TTFont(sys.argv[1], fontNumber=1)  # KR face in upstream Noto CJK collection
options = subset.Options()
options.flavor = 'woff'
subsetter = subset.Subsetter(options=options)
subsetter.populate(unicodes=list(range(0x20, 0x100)) + list(range(0x1100, 0x1200)) +
                   list(range(0x3130, 0x3190)) + list(range(0xAC00, 0xD7A4)) +
                   list(range(0x2000, 0x2070)))
subsetter.subset(font)
for record in font['name'].names:
    if record.nameID in (1, 3, 4, 6, 16, 17):
        value = 'Regular' if record.nameID == 17 else 'OpenShortsKoreanUI' if record.nameID == 6 else 'OpenShorts Korean UI'
        record.string = value.encode(record.getEncoding())
font.flavor = 'woff'
font.save(Path(__file__).resolve().parents[1] / 'public/fonts/openshorts-korean-ui.woff')
