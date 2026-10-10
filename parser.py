# -*- coding: utf-8 -*-
"""영문 봇 메시지에서 확전 정보를 뽑아낸다.

원문은 두 가지 형태로 온다.

  (구형)  Daily Escalation Target Loot - 2026-06-02
          Missions
          The Tombs: Legatus S.p.A. [Brand Set]
          Vendor Caches
          Gear: Backpacks

  (8월형)  **Daily Escalation Target Loot** | (이모지) **2026-08-13**
          **Missions:**
          * **Wall Street**: Golan Gear Ltd
          **Escalation Vendor Requisition:**
          * **Weapon Cache**: Rifles

  (10월형) 🎯 **Daily Escalation Target Loot · 2026-10-10**
          **Missions:**
          <:cleaners:1557773297385742446> **Pathway Park**
          ↳ China Light Industries <:chinalight:155777...>
          **Escalation Vendor Caches:**
          • **Weapon Cache:** Assault Rifles <:ar:155777...>
          ProtoTrack: https://prototrack.gg/

10월형은 미션과 전리품이 두 줄로 나뉘고, 이름마다 디스코드 커스텀 이모지가
붙는다. 커스텀 이모지의 원문 표기 <:이름:숫자> 에 콜론이 들어 있어서, 걷어내지
않으면 "콜론 앞 = 미션" 규칙이 이모지 한가운데서 잘린다. 2026-10-01 무렵부터
열흘 가까이 그렇게 잘린 조각이 그대로 그림과 사전에 들어갔다.

주간 로테이션 줄은 읽지 않는다. v13 이미지에 넣지 않기로 했다.
시각은 본문에 없어서 디스코드 메시지 타임스탬프를 쓴다.
"""
import re

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

VENDOR_HEAD = (r"(?:Escalation\s+Vendor\s+Requisition|Escalation\s+Requisition\s+Vendor"
               r"|Escalation\s+Vendor\s+Caches?|Vendor\s+Caches?)")
MISSIONS_RE = re.compile(
    r"Missions?\s*:?\s*\n(.*?)(?=" + VENDOR_HEAD + r"\s*:?|\Z)",
    re.S | re.I,
)
VENDOR_RE = re.compile(VENDOR_HEAD + r"\s*:?\s*\n(.*)", re.S | re.I)
LINE_RE = re.compile(r"^(.+?)\s*:\s*(.+?)\s*$")
BRACKET_RE = re.compile(r"\s*\[([^\]]+)\]\s*$")

BULLET_RE = re.compile(r"^[\s*\-•·◆▪→>]+")

# 디스코드 커스텀 이모지. API 원문은 <:이름:숫자>, 손으로 복사하면 :이름: 이 된다.
CUSTOM_EMOJI_RE = re.compile(r"<a?:[\w~]+:\d+>")
SHORTCODE_RE = re.compile(r"(?<![\w/]):[A-Za-z_][\w~]*:(?![\w/])")
# 10월형에서 미션 이름 다음 줄의 전리품 앞에 붙는 화살표
LOOT_ARROW_RE = re.compile(r"^\s*[↳⤷└╰➥]\s*")
# 미션·전리품 이름에 나올 리 없는 것. 걸리면 형식이 또 바뀐 것이니 버린다.
SUSPICIOUS_RE = re.compile(r"[<>]|https?:|//|\d{6,}")
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
    # 이모지 안의 콜론이 '미션: 전리품' 구분과 섞이지 않게 가장 먼저 걷어낸다
    s = CUSTOM_EMOJI_RE.sub(" ", s)
    s = SHORTCODE_RE.sub(" ", s)
    # 화살표는 아래 EMOJI_RE 범위에 들어 있어 지워지기 전에 처리해야 한다
    s = "\n".join(_join_arrows(s.split("\n")))
    s = MD_RE.sub("", s)
    s = EMOJI_RE.sub(" ", s)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    return "\n".join(lines)


def _join_arrows(lines):
    """'미션' 다음 줄의 '↳ 전리품'을 '미션: 전리품' 한 줄로 합친다."""
    out = []
    for ln in lines:
        m = LOOT_ARROW_RE.match(ln)
        if m:
            j = len(out) - 1
            while j >= 0 and not out[j].strip():
                j -= 1
            if j >= 0:
                out[j] = out[j].rstrip() + ": " + ln[m.end():].strip()
                continue
        out.append(ln)
    return out


def _rows(block):
    out = []
    for raw in block.split("\n"):
        line = BULLET_RE.sub("", raw).strip()
        if not line or ":" not in line:
            continue
        if SUSPICIOUS_RE.search(line):
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
