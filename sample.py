# -*- coding: utf-8 -*-
"""렌더러 확인용 표본 — 2026-08-13 실제 확전.

세트 효과는 data/set_effects.json에서 읽어온다. 나중에 파서가 만들 구조와 같다.
"""
import json
import sys

import config as cfg
import renderer

with open(cfg.DATA / "set_effects.json", encoding="utf-8") as f:
    FX = json.load(f)

ICON = {
    "골란 기어 유한회사": "보호장구/Golan.png",
    "메저드 어셈블리": "보호장구 세트/Measured Assembly.png",
    "페트로프 방위 그룹": "보호장구/Petrov.png",
    "합스부르크 가드": "보호장구/Habsburg Guard.png",
    "권총집": "보호장구 일반/Holster_icon.png",
    "소총": "무기/Rifles_TD2.png",
}
CATEGORY = {
    "골란 기어 유한회사": "브랜드 세트",
    "메저드 어셈블리": "보호장구 세트",
    "페트로프 방위 그룹": "브랜드 세트",
    "합스부르크 가드": "브랜드 세트",
    "권총집": "보호장구",
    "소총": "무기",
}


def _find(ko):
    """한글 이름으로 세트 효과를 찾는다. 없으면 None."""
    for group in ("gear_sets", "brand_sets"):
        for entry in FX[group].values():
            if entry.get("ko") == ko:
                return entry
    return None


def effect_card(ko):
    entry = _find(ko)
    card = {"name": ko, "category": CATEGORY.get(ko, ""), "icon": ICON.get(ko)}
    if entry is None or entry.get("source") == "MISSING" or not entry.get("tiers"):
        card["pending"] = True
        card["tiers"] = []
    else:
        card["tiers"] = entry["tiers"]
    return card


def build():
    missions = [
        ("월스트리트", "골란 기어 유한회사"),
        ("루즈벨트 섬", "메저드 어셈블리"),
        ("질병통제본부", "페트로프 방위 그룹"),
        ("항공우주 박물관", "합스부르크 가드"),
        ("디스트릭트 유니온 아레나", "권총집"),
    ]
    vendor = [
        ("프로토타입 장비 상자", "권총집"),
        ("프로토타입 무기 상자", "소총"),
    ]
    has_effect = ("보호장구 세트", "브랜드 세트")
    return {
        "date": "2026-08-13",
        "kst": "17:01",
        "utc": "08:01",
        "missions": [
            {"mission": m, "loot": l, "category": CATEGORY[l], "icon": ICON[l]}
            for m, l in missions
        ],
        "vendor": [
            {"type": t, "loot": l, "category": CATEGORY[l], "icon": ICON[l]}
            for t, l in vendor
        ],
        "effects": [effect_card(l) for _, l in missions
                    if CATEGORY[l] in has_effect],
        "no_effect": sorted({l for _, l in missions + vendor
                             if CATEGORY[l] not in has_effect}),
    }


if __name__ == "__main__":
    data = build()
    img = renderer.render(data)
    cfg.OUT.mkdir(parents=True, exist_ok=True)
    out = cfg.OUT / "escalation_2026-08-13.png"
    img.save(out)
    print("저장:", out)
    print("크기: %d x %d" % img.size)
    pending = [c["name"] for c in data["effects"] if c.get("pending")]
    if pending:
        print("효과 없음:", ", ".join(pending), file=sys.stderr)
