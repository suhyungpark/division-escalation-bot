# -*- coding: utf-8 -*-
"""Red Horizon 패치(PvE 기준)의 세트 보너스를 반영한다.

패치 노트가 영문이라 인게임 한글로 옮겨야 하는데, 용어를 새로 지어내지 않는다.
GLOSSARY는 전부 이미 인게임 화면이나 나무위키로 확인된 표기에서 가져왔다.
못 옮기는 용어가 있으면 조용히 넘어가지 않고 목록으로 보여준다.
"""
import json
import sys

import config as cfg

# 영문 스탯 -> 인게임 한글. 근거가 있는 것만 적는다.
GLOSSARY = {
    "Weapon Damage": "무기 대미지",
    "Weapon Handling": "무기 조작력",
    "Total Armor": "전체 방어도",
    "Armor Regen": "방어도 재생",
    "Armor on Kill": "적 처치 시 방어도 회복",
    "Health": "생명력",
    "Skill Damage": "스킬 대미지",
    "Skill Haste": "스킬 가속",
    "Skill Duration": "스킬 지속 시간",
    "Skill Efficiency": "스킬 효율",
    "Skill Health": "스킬 생명력",
    "Skill Tier": "스킬 등급",
    "Repair Skills": "스킬 회복",
    "Status Effect": "상태이상 효과",
    "Status Effects": "상태이상 효과",
    "Explosive Damage": "폭발물 대미지",
    "Explosive Resistance": "폭발물 저항",
    "Pulse Resistance": "펄스 저항",
    "Critical Hit Chance": "치명타 확률",
    "Critical Hit Damage": "치명타 대미지",
    "Headshot Damage": "헤드샷 대미지",
    "Damage to Armor": "방어도 대상 대미지",
    "Damage to Health": "생명력 대상 대미지",
    "Magazine Size": "탄창 용량",
    "Ammo Capacity": "탄약 휴대량",
    "Reload Speed": "재장전 속도",
    "Rate of Fire": "발사 속도",
    "Accuracy": "명중률",
    "Stability": "안정성",
    "Optimal Range": "적정 사거리",
    "Increased Threat": "위협 수준 증가",
    "AR Damage": "돌격소총 대미지",
    "SMG Damage": "기관단총 대미지",
    "LMG Damage": "경기관총 대미지",
    "MMR Damage": "지정사수소총 대미지",
    "Rifle Damage": "소총 대미지",
    "Shotgun Damage": "산탄총 대미지",
    "Pistol Damage": "권총 대미지",
    # 아래 둘은 나무위키 브랜드 표에서 옮겼다. 인게임 캡처는 아직 없다.
    # 대조군으로 길라 가드(인게임 확인)를 함께 뽑아 세 줄이 우리 값과 맞는 것을
    # 확인한 뒤 반영했다. 게임 화면과 다르면 여기만 고치고 다시 돌리면 된다.
    "Hazard Protection": "상태이상 저항",
    "Protection from Elites": "정예 대상 방호도",
}

# (수치, 스탯) 세 쌍. 패치 노트 PvE 열 그대로.
BRANDS = {
    "Alps Summit Armaments":   [(18, "Repair Skills"), (30, "Skill Duration"), (30, "Skill Haste")],
    "China Light Industries":  [(15, "Explosive Damage"), (20, "Status Effect"), (30, "Skill Haste")],
    "Electrique":              [(10, "Status Effects"), (20, "Hazard Protection"), (8, "Skill Efficiency")],
    "Empress International":   [(10, "Skill Health"), (13, "Skill Damage"), (8, "Skill Efficiency")],
    "Hana-U Corporation":      [(10, "Skill Haste"), (13, "Skill Damage"), (18, "Weapon Damage")],
    "Murakami Industries":     [(15, "Skill Duration"), (35, "Repair Skills"), (18, "Skill Damage")],
    "Richter & Kaiser GmbH":   [(10, "Skill Haste"), (40, "Explosive Resistance"), (52, "Repair Skills")],
    "Shiny Monkey Gear":       [(15, "Skill Duration"), (5, "Skill Efficiency"), (52, "Repair Skills")],
    "Edelweiss GPz":           [(18, "Repair Skills"), (20, "Skill Haste"), (8, "Skill Efficiency")],
    "Wyvern Wear":             [(8, "Skill Damage"), (20, "Status Effects"), (45, "Skill Duration")],
    "5.11 Tactical":           [(10, "Protection from Elites"), (100, "Increased Threat"), (30, "Hazard Protection")],
    "Badger Tuff":             [(12, "Shotgun Damage"), (10, "Armor on Kill"), (15, "Total Armor")],
    "Belstone Armory":         [(1, "Armor Regen"), (100, "Increased Threat"), (30, "Protection from Elites")],
    "Brazos de Arcabuz":       [(10, "Skill Haste"), (1, "Skill Tier"), (50, "Magazine Size")],
    "Gila Guard":              [(5, "Total Armor"), (20, "Hazard Protection"), (2, "Armor Regen")],
    "Golan Gear Ltd":          [(20, "Explosive Resistance"), (1.5, "Armor Regen"), (150, "Increased Threat")],
    "Habsburg Guard":          [(13, "Headshot Damage"), (24, "MMR Damage"), (25, "Status Effects")],
    "Palisade Steelworks":     [(10, "Armor on Kill"), (20, "Protection from Elites"), (1, "Skill Tier")],
    "Lengmo":                  [(15, "Reload Speed"), (24, "LMG Damage"), (30, "Weapon Handling")],
    "Uzina Getica":            [(5, "Total Armor"), (10, "Armor on Kill"), (30, "Hazard Protection")],
    "Yaahl Gear":              [(10, "Hazard Protection"), (12, "Weapon Damage"), (40, "Pulse Resistance")],
    "Airaldi Holdings":        [(12, "MMR Damage"), (26, "Headshot Damage"), (5, "Damage to Armor")],
    "Unit Alloys":             [(5, "Rate of Fire"), (24, "AR Damage"), (50, "Magazine Size")],
    "Ceska Vyroba S.R.O.":     [(8, "Critical Hit Chance"), (24, "Shotgun Damage"), (30, "Hazard Protection")],
    "Douglas & Harding":       [(24, "Pistol Damage"), (20, "Skill Health"), (50, "Accuracy")],
    "Fenris Group AB":         [(12, "AR Damage"), (32, "Magazine Size"), (50, "Stability")],
    "Grupo Sombra S.A.":       [(13, "Critical Hit Damage"), (20, "Explosive Damage"), (39, "Headshot Damage")],
    "Imminence Armaments":     [(6, "Weapon Damage"), (48, "Pistol Damage"), (30, "Skill Health")],
    "Legatus S.p.A.":          [(15, "Magazine Size"), (24, "SMG Damage"), (105, "Optimal Range")],
    "Petrov Defense Group":    [(12, "LMG Damage"), (15, "Weapon Handling"), (50, "Ammo Capacity")],
    "Providence Defense":      [(13, "Headshot Damage"), (8, "Critical Hit Chance"), (13, "Critical Hit Damage")],
    "Overlord Armaments":      [(12, "Rifle Damage"), (30, "Accuracy"), (30, "Weapon Handling")],
    "Royal Works":             [(5, "Weapon Handling"), (24, "LMG Damage"), (50, "Accuracy")],
    "Sokolov Concern":         [(12, "SMG Damage"), (13, "Critical Hit Damage"), (8, "Critical Hit Chance")],
    "Urban Lookout":           [(5, "Weapon Handling"), (24, "MMR Damage"), (45, "Skill Duration")],
    "Walker, Harris & Co":     [(6, "Weapon Damage"), (5, "Damage to Armor"), (10, "Damage to Health")],
    "Zwiadowka Sp. z o.o":     [(15, "Magazine Size"), (24, "Rifle Damage"), (30, "Weapon Handling")],
}

# 보호장구 세트는 2부위·3부위만 재조정됐다. 4부위 특성은 손대지 않는다.
GEAR = {
    "True Patriot":     [[(15, "Weapon Handling")], [(30, "Magazine Size")]],
    "Aces & Eights":    [[(30, "MMR Damage"), (30, "Rifle Damage")],
                         [(30, "Headshot Damage"), (30, "Weapon Handling")]],
    "Breaking Point":   [[(30, "Rifle Damage"), (30, "MMR Damage")],
                         [(30, "Headshot Damage"), (30, "Weapon Handling")]],
    "Hotshot":          [[(30, "MMR Damage")],
                         [(30, "Headshot Damage"), (30, "Weapon Handling")]],
    "Ember Engine":     [[(8, "Skill Efficiency")], [(30, "Status Effects")]],
}


def fmt(pct, stat):
    ko = GLOSSARY.get(stat)
    if ko is None:
        return None
    if stat == "Skill Tier":
        return "+%g %s" % (pct, ko)
    return "+%.1f%% %s" % (pct, ko)


def render(pairs):
    parts = [fmt(p, s) for p, s in pairs]
    if any(x is None for x in parts):
        return None
    return " · ".join(parts)


def main():
    path = cfg.DATA / "set_effects.json"
    fx = json.loads(path.read_text(encoding="utf-8"))
    changed, unmapped, added = [], set(), []

    for eng, trio in BRANDS.items():
        lines = [fmt(p, s) for p, s in trio]
        if any(x is None for x in lines):
            unmapped.update(s for (p, s) in trio if GLOSSARY.get(s) is None)
            continue
        cur = fx["brand_sets"].get(eng)
        old = [t.get("text") for t in (cur or {}).get("tiers", [])]
        if cur is None:
            added.append(eng)
        elif old != lines:
            changed.append((cur.get("ko", eng), old, lines))
        entry = cur or {"ko": eng, "core_attribute": ""}
        entry["source"] = "patch-pve"
        entry["tiers"] = [{"n": i + 1, "text": t} for i, t in enumerate(lines)]
        entry.pop("_todo", None)
        fx["brand_sets"][eng] = entry

    for eng, (two, three) in GEAR.items():
        l2, l3 = render(two), render(three)
        if l2 is None or l3 is None:
            unmapped.update(s for grp in (two, three) for (p, s) in grp
                            if GLOSSARY.get(s) is None)
            continue
        cur = fx["gear_sets"].get(eng)
        if cur is None:
            fx["gear_sets"][eng] = {"ko": eng, "source": "patch-pve", "tiers": []}
            cur = fx["gear_sets"][eng]
            added.append(eng)
        old = [t.get("text") for t in cur.get("tiers", []) if not t.get("talent")]
        if old and old != [l2, l3]:
            changed.append((cur.get("ko", eng), old, [l2, l3]))
        talent = next((t for t in cur.get("tiers", []) if t.get("talent")), None)
        cur["tiers"] = [{"n": 2, "text": l2}, {"n": 3, "text": l3}]
        if talent:
            cur["tiers"].append(talent)
        cur["source"] = "patch-pve"

    note = "2026-08-27 Red Horizon 패치 반영. 세트 보너스는 PvE 수치 기준."
    if note not in fx["_note"]:
        fx["_note"].append(note)
    path.write_text(json.dumps(fx, ensure_ascii=False, indent=2), encoding="utf-8")

    print("바뀐 항목 %d개" % len(changed))
    for ko, old, new in changed:
        print("  %s" % ko)
        for o, n in zip(old + [""] * 3, new):
            if o != n:
                print("     %-40s -> %s" % (o or "(없음)", n))
    if added:
        print("\n새로 들어온 항목: %s" % ", ".join(added))
    if unmapped:
        print("\n인게임 표기를 모르는 용어 %d개 — 해당 세트는 손대지 않았다:" % len(unmapped))
        for s in sorted(unmapped):
            print("   %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
