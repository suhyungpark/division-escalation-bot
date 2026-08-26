# -*- coding: utf-8 -*-
"""글자와 도형을 다루는 최소 도구.

Pillow에는 자간도 굵은글씨 혼용도 줄바꿈도 없어서 직접 만든다.
"""
import re
from PIL import ImageFont

_BOLD_PAT = re.compile(r"\*\*(.+?)\*\*", re.S)
# 수치는 눈에 띄어야 훑을 수 있다. 퍼센트·초·부호 붙은 수만 자동으로 굵게.
_NUM_PAT = re.compile(r"([+\-]?\d+(?:\.\d+)?%|\d+초|[+\-]\d+(?:\.\d+)?)")

# 한글은 이미 정폭이라 라틴만큼 자간을 벌리면 낱글자가 흩어져 보인다.
HANGUL_TRACKING = 0.4


def load_font(candidates, size):
    for p in candidates:
        try:
            return ImageFont.truetype(str(p), size)
        except OSError:
            continue
    raise FileNotFoundError("쓸 수 있는 폰트가 없습니다: %s" % (candidates,))


def line_height(font):
    a, d = font.getmetrics()
    return a + d


def _is_hangul(ch):
    return "가" <= ch <= "힣" or "㄰" <= ch <= "㆏"


def _tracking(ch, ls):
    if not ls:
        return 0.0
    return ls * (HANGUL_TRACKING if _is_hangul(ch) else 1.0)


def width_of(draw, s, font, ls=0.0):
    """draw_ls가 실제로 그리는 폭과 정확히 같은 값을 낸다 (우측 정렬용)."""
    if not s:
        return 0.0
    if not ls:
        return draw.textlength(s, font=font)
    total = 0.0
    for i, ch in enumerate(s):
        total += draw.textlength(ch, font=font)
        if i < len(s) - 1:
            total += _tracking(ch, ls)
    return total


def draw_ls(draw, xy, s, font, fill, ls=0.0, anchor="lm"):
    """자간을 준 글자. ls가 0이면 통째로 한 번에 그린다."""
    if not ls:
        draw.text(xy, s, font=font, fill=fill, anchor=anchor)
        return draw.textlength(s, font=font)
    x, y = xy
    for i, ch in enumerate(s):
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += draw.textlength(ch, font=font)
        if i < len(s) - 1:
            x += _tracking(ch, ls)
    return x - xy[0]


def emphasize(text):
    """이미 **로 표시된 곳이 없으면 수치를 찾아 굵게 표시한다."""
    if "**" in text:
        return text
    return _NUM_PAT.sub(r"**\1**", text)


def parse_rich(text):
    """'앞 **굵게** 뒤' -> [('앞 ', False), ('굵게', True), (' 뒤', False)]"""
    out, pos = [], 0
    for m in _BOLD_PAT.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(1), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return [(t, b) for t, b in out if t]


def _seg_width(draw, s, font):
    return draw.textlength(s, font=font)


def wrap_rich(draw, segs, font_r, font_b, max_w):
    """굵기가 섞인 글을 max_w 안에서 줄바꿈. 띄어쓰기에서 끊고, 안 되면 글자 단위로."""
    lines, cur, cur_w = [], [], 0.0

    def flush():
        nonlocal cur, cur_w
        if cur:
            lines.append(cur)
        cur, cur_w = [], 0.0

    for text, bold in segs:
        font = font_b if bold else font_r
        tokens = re.split(r"(\s+)", text)
        for tok in tokens:
            if not tok:
                continue
            w = _seg_width(draw, tok, font)
            if cur_w + w <= max_w or (not cur and tok.isspace()):
                if tok.isspace() and not cur:
                    continue          # 줄 첫머리의 공백은 버린다
                cur.append((tok, bold))
                cur_w += w
                continue
            if tok.isspace():
                flush()
                continue
            if w <= max_w:
                flush()
                cur.append((tok, bold))
                cur_w = w
                continue
            # 한 덩어리가 줄보다 길면 글자 단위로 쪼갠다
            for ch in tok:
                cw = _seg_width(draw, ch, font)
                if cur_w + cw > max_w:
                    flush()
                cur.append((ch, bold))
                cur_w += cw
    flush()
    return lines


def draw_rich_line(draw, xy, line, font_r, font_b, fill, fill_bold, anchor="lm"):
    x, y = xy
    for text, bold in line:
        font = font_b if bold else font_r
        draw.text((x, y), text, font=font,
                  fill=(fill_bold if bold else fill), anchor=anchor)
        x += _seg_width(draw, text, font)
    return x - xy[0]


def chamfer_points(box, cut):
    """모서리를 깎은 사각형. 오른쪽 위와 왼쪽 아래를 자른다 — 디비전 UI 문법."""
    x0, y0, x1, y1 = box
    return [
        (x0, y0), (x1 - cut, y0), (x1, y0 + cut),
        (x1, y1), (x0 + cut, y1), (x0, y1 - cut),
    ]


def chamfer_rect(draw, box, cut, fill=None, outline=None, width=1):
    pts = chamfer_points(box, cut)
    if fill:
        draw.polygon(pts, fill=fill)
    if outline:
        draw.line(pts + [pts[0]], fill=outline, width=width, joint="curve")
