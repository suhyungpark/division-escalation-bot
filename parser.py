# -*- coding: utf-8 -*-
"""영문 봇 메시지에서 확전 정보를 뽑아낸다.

원문은 두 가지 형태로 온다.

  (구형)  Daily Escalation Target Loot - 2026-06-02
          Missions
          The Tombs: Legatus S.p.A. [Brand Set]
          Vendor Caches
          Gear: Backpacks

  (신형)  **Daily Escalation Target Loot** | (이모지) **2026-08-13**
          **Missions:**
          * **Wall Street**: Golan Gear Ltd
          **Escalation Vendor Requisition:**
          * **Weapon Cache**: Rifles

주간 로테이션 줄은 읽지 않는다. v13 이미지에 넣지 않기로 했다.
시각은 본문에 없어서 디스코드 메시지 타임스탬프를 쓴다.
"""
import re

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

MISSIONS_RE = re.compile(
    r"Missions?\s*:?\s*\n(.*?)"
    r"(?=(?:Escalation\s+Vendor\s+Requisition|Escalation\s+Requisition\s+Vendor"
    r"|Vendor\s+Caches?)\s*:?|\Z)",
    re.S | re.I,
)
VENDOR_RE = re.compile(
    r"(?:Escalation\s+Vendor\s+Requisition|Escalation\s+Requisition\s+Vendor"
    r"|Vendor\s+Caches?)\s*:?\s*\n(.*)",
    re.S | re.I,
)
LINE_RE = re.compile(r"^(.+?)\s*:\s*(.+?)\s*$")
BRACKET_RE = re.compile(r"\s*\[([^\]]+)\]\s*$")

BULLET_RE = re.compile(r"^[\s*\-•·◆▪→>]+")
MD_RE = re.compile(r"\*+|`+|__")
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "←-⇿"
    "⌀-➿"
    "⬀-⯿"
    "️‍"
    "]+"
)

VENDOR_ALIAS = {
    "weapon": "Weapon Cache",
    "weapons": "Weapon Cache",
    "weapon cache": "Weapon Cache",
    "prototype weapon cache": "Weapon Cache",
    "gear": "Gear Cache",
    "gear cache": "Gear Cache",
    "prototype gear cache": "Gear Cache",
}
# 원문 순서와 무관하게 장비 상자를 먼저 보여준다 (원본 이미지 순서)
VENDOR_ORDER = ["Gear Cache", "Weapon Cache"]


def prepare(text):
    """마크다운과 이모지를 걷어내되 줄 구조는 살린다.

    블록을 찾는 정규식이 줄바꿈에 기대고 있어서 공백을 통째로 뭉개면 안 된다.
    줄 안쪽 공백만 정리한다.
    """
    s = text.replace("\r\n", "\n")
    s = MD_RE.sub("", s)
    s = EMOJI_RE.sub(" ", s)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    return "\n".join(lines)


def _rows(block):
    out = []
    for raw in block.split("\n"):
        line = BULLET_RE.sub("", raw).strip()
        if not line or ":" not in line:
            continue
        hint = ""
        m = BRACKET_RE.search(line)
        if m:
            hint = m.group(1).strip()
            line = BRACKET_RE.sub("", line)
        m = LINE_RE.match(line)
        if not m:
            continue
        left, right = m.group(1).strip(), m.group(2).strip()
        if not left or not right:
            continue
        out.append((left, right, hint))
    return out


def parse(text):
    """파싱 실패하면 None. 확전 메시지가 아니라는 뜻이다."""
    if not text:
        return None
    flat = prepare(text)
    if not re.search(r"Escalation", flat, re.I):
        return None

    m = DATE_RE.search(flat)
    if not m:
        return None
    date = "%s-%s-%s" % m.groups()

    mm = MISSIONS_RE.search(flat)
    if not mm:
        return None
    missions = [
        {"mission_en": a, "loot_en": b, "category_hint": h}
        for a, b, h in _rows(mm.group(1))
    ]
    if not missions:
        return None

    vendor = []
    vm = VENDOR_RE.search(flat)
    if vm:
        seen = {}
        for a, b, _h in _rows(vm.group(1)):
            key = VENDOR_ALIAS.get(a.lower(), a)
            seen[key] = b
        for key in VENDOR_ORDER:
            if key in seen:
                vendor.append({"type_en": key, "loot_en": seen.pop(key)})
        for key, val in seen.items():
            vendor.append({"type_en": key, "loot_en": val})

    return {"date": date, "missions": missions, "vendor": vendor}
