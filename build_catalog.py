# -*- coding: utf-8 -*-
"""아이템 카탈로그를 만든다 (빌드 시 1회).

영문 이름 하나로 한글·카테고리·아이콘 경로가 전부 나오는 표를 만든다.
이름과 파일명이 제각각이라(Gila Guard ↔ Gila.png, Marksman ↔ Marskman 오타)
맞추는 일은 여기서 다 끝내고, 실행 중에는 그냥 조회만 한다.

  python build_catalog.py
"""
import difflib
import json
import re
import sys
import unicodedata

import config as cfg

FOLDER_CATEGORY = {
    "보호장구 세트": "보호장구 세트",
    "보호장구": "브랜드 세트",
    "보호장구 일반": "보호장구",
    "무기": "무기",
}

# 이름과 파일명이 전혀 안 닮은 것들. 자동 매칭이 못 잡는 경우만 적는다.
# 키는 norm()을 거친 뒤 단수형으로 줄인 값이라 Holster/Holsters 둘 다 걸린다.
ICON_HINT = {
    "backpack":        "보호장구 일반/Bag_icon.png",
    "chestpiece":      "보호장구 일반/Armor_icon.png",
    "bodyarmor":       "보호장구 일반/Armor_icon.png",
    "mask":            "보호장구 일반/Mask_icon.png",
    "glove":           "보호장구 일반/Gloves_icon.png",
    "holster":         "보호장구 일반/Holster_icon.png",
    "kneepad":         "보호장구 일반/Kneepads_icon.png",
    "gearmod":         "보호장구 일반/GearMods_icon.png",
    "skillmod":        "보호장구 일반/SkillMods_icon.png",
    "lightmachinegun": "무기/LMGs_TD2.png",
    "lmg":             "무기/LMGs_TD2.png",
    "submachinegun":   "무기/SMGs_TD2.png",
    "smg":             "무기/SMGs_TD2.png",
    "marksmanrifle":   "무기/Marskman_Rifles_TD2.png",
    "mmr":             "무기/Marskman_Rifles_TD2.png",
    "assaultrifle":    "무기/Assault_Rifles_TD2.png",
    "rifle":           "무기/Rifles_TD2.png",
    "shotgun":         "무기/Shotguns_TD2.png",
    "pistol":          "무기/Pistols_TD2.png",
}


def norm(s):
    """비교용으로 납작하게 만든다. 대소문자·기호·아포스트로피를 전부 지운다."""
    s = unicodedata.normalize("NFKD", s).lower()
    s = s.replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", s)


def depluralise(n):
    return n[:-1] if len(n) > 3 and n.endswith("s") else n


def scan_icons():
    out = []
    for folder, category in FOLDER_CATEGORY.items():
        d = cfg.ICONS / folder
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.png")):
            out.append({
                "rel": "%s/%s" % (folder, p.name),
                "stem": p.stem,
                "norm": norm(p.stem),
                "category": category,
            })
    return out


def match_icon(english, category, icons):
    """이름 -> 아이콘. 정확·접두·근사 순으로 좁혀간다."""
    n = norm(english)
    hint = ICON_HINT.get(depluralise(n)) or ICON_HINT.get(n)
    if hint:
        return hint, "hint"
    pool = [i for i in icons if i["category"] == category] or icons

    for i in pool:
        if i["norm"] == n:
            return i["rel"], "exact"
    # 파일명이 짧게 줄어든 경우(Gila Guard -> Gila)와 꼬리가 붙은 경우(Pistols_TD2)
    cands = [i for i in pool if n.startswith(i["norm"]) or i["norm"].startswith(n)]
    if len(cands) == 1:
        return cands[0]["rel"], "prefix"
    if len(cands) > 1:
        best = max(cands, key=lambda i: len(i["norm"]))
        return best["rel"], "prefix*"
    # 오타까지 흡수 (Marksman <-> Marskman)
    best, score = None, 0.0
    for i in pool:
        r = difflib.SequenceMatcher(None, n, i["norm"]).ratio()
        if r > score:
            best, score = i, r
    if best and score >= 0.72:
        return best["rel"], "fuzzy %.2f" % score
    return None, "none"


def main():
    with open(cfg.DATA / "translation_table.json", encoding="utf-8") as f:
        table = json.load(f)
    ov_path = cfg.DATA / "overrides.json"
    overrides = {}
    if ov_path.exists():
        with open(ov_path, encoding="utf-8") as f:
            overrides = json.load(f)

    items = dict(table.get("items", {}))
    cats = dict(table.get("item_categories", {}))
    missions = dict(table.get("missions", {}))

    items.update(overrides.get("items", {}))
    cats.update(overrides.get("item_categories", {}))
    missions.update(overrides.get("missions", {}))
    drop = set(overrides.get("drop_items", []))
    no_icon_ok = set(overrides.get("allow_no_icon", []))
    review = set(overrides.get("needs_review", []))
    for k in drop:
        items.pop(k, None)
        cats.pop(k, None)

    # v12는 영문 카테고리를 썼다. 인게임 표기로 옮긴다.
    CAT_KO = {
        "Gear Set": "보호장구 세트",
        "Brand Set": "브랜드 세트",
        "Gear": "보호장구",
        "Weapon": "무기",
        "Named": "고유장비",
        "Exotic": "특급장비",
    }

    icons = scan_icons()
    catalog, report = {}, []
    used = set()
    for eng, ko in sorted(items.items()):
        cat_raw = cats.get(eng, "")
        category = CAT_KO.get(cat_raw, cat_raw)
        rel, how = match_icon(eng, category, icons)
        if rel:
            used.add(rel)
            # 아이콘이 든 폴더가 카테고리의 가장 믿을 만한 근거다.
            # v12 사전은 오티즈·핫샷 같은 세트를 'Named'로 잘못 적어놨다.
            folder = rel.split("/")[0]
            if folder in FOLDER_CATEGORY:
                category = FOLDER_CATEGORY[folder]
        entry = {"ko": ko, "category": category, "icon": rel}
        if eng in review:
            entry["review"] = True
        catalog[eng] = entry
        noisy = (not category) or (not rel and eng not in no_icon_ok)
        if noisy or how.startswith("fuzzy") or how == "prefix*":
            report.append((eng, ko, category or "(없음)", rel or "(없음)", how))

    orphan = [i["rel"] for i in icons if i["rel"] not in used]

    out = {
        "_note": "build_catalog.py가 만든 파일. 직접 고치지 말고 overrides.json을 고칠 것.",
        "missions": missions,
        "items": catalog,
    }
    with open(cfg.DATA / "catalog.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("임무 %d개 · 아이템 %d개 · 아이콘 %d개" % (len(missions), len(catalog), len(icons)))
    if report:
        print("\n[확인 필요 %d건]" % len(report))
        for eng, ko, cat, rel, how in report:
            print("  %-34s %-16s %-12s %-40s %s" % (eng, ko, cat, rel, how))
    if orphan:
        print("\n[아이템이 가리키지 않는 아이콘 %d개]" % len(orphan))
        for r in orphan:
            print("  " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
