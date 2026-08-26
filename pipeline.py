# -*- coding: utf-8 -*-
"""파싱 결과를 렌더러가 먹는 모양으로 바꾼다.

여기서 세 가지가 갈린다.
  - 세트 효과가 원래 없는 것 (무기·보호장구 부위) -> 카드 없이 하단 한 줄
  - 있어야 하는데 데이터가 없는 것                -> '준비 중' 카드 + 알림
  - 사전에 없어서 기계번역한 것                   -> 회색+별표 + 알림
"""
import datetime as _dt
import json

import config as cfg
import translator as tr

SET_CATEGORIES = ("보호장구 세트", "브랜드 세트")
KST = _dt.timezone(_dt.timedelta(hours=9))


def load_effects(path=None):
    """세트 효과를 정규화한 이름으로 찾을 수 있게 색인한다.

    사전과 효과 데이터의 영문 표기가 미묘하게 다를 수 있어서
    (China Light Industries / ... Corporation) 번역기와 같은 방식으로 찾는다.
    """
    with open(path or (cfg.DATA / "set_effects.json"), encoding="utf-8") as f:
        raw = json.load(f)
    index = {}
    for group in ("gear_sets", "brand_sets"):
        for eng, entry in raw.get(group, {}).items():
            index.setdefault(tr.norm(eng), entry)
            index.setdefault(tr.depluralise(tr.norm(eng)), entry)
    return index


class Pipeline:
    def __init__(self, translator=None, effects=None):
        self.tr = translator or tr.Translator()
        self.fx = effects if effects is not None else load_effects()

    def _effect_for(self, english):
        n = tr.norm(english)
        hit = self.fx.get(n) or self.fx.get(tr.depluralise(n))
        if hit:
            return hit
        import difflib
        near = difflib.get_close_matches(n, list(self.fx), n=1, cutoff=tr.FUZZY_MIN)
        return self.fx[near[0]] if near else None

    def build(self, parsed, when_utc):
        notices = []
        utc = when_utc.astimezone(_dt.timezone.utc)
        kst = utc.astimezone(KST)

        missions, vendor = [], []
        seen_names = []          # 카드 중복 방지
        effects, no_effect = [], []

        for row in parsed["missions"]:
            m = self.tr.mission(row["mission_en"])
            it = self.tr.item(row["loot_en"])
            category = it.category or row.get("category_hint", "")
            missions.append({
                "mission": m.ko, "loot": it.ko, "category": category,
                "icon": it.icon, "auto": it.flagged() or m.flagged(),
            })
            if category in SET_CATEGORIES:
                if it.ko in seen_names:
                    continue
                seen_names.append(it.ko)
                effects.append(self._card(it, category, notices))
            elif it.ko not in no_effect:
                no_effect.append(it.ko)

        for row in parsed.get("vendor", []):
            t = self.tr.item(row["type_en"])
            it = self.tr.item(row["loot_en"])
            vendor.append({
                "type": t.ko, "loot": it.ko, "category": it.category,
                "icon": it.icon, "auto": it.flagged(),
            })
            if it.category not in SET_CATEGORIES and it.ko not in no_effect:
                no_effect.append(it.ko)

        for eng in self.tr.unknown:
            notices.append("사전에 없고 기계번역도 실패: **%s** — 원문 그대로 나갑니다" % eng)
        for eng, ko in self.tr.pending:
            notices.append("기계번역으로 채움: **%s** → %s — 확인 부탁드립니다" % (eng, ko))

        data = {
            "date": parsed["date"],
            "kst": kst.strftime("%H:%M"),
            "utc": utc.strftime("%H:%M"),
            "missions": missions,
            "vendor": vendor,
            "effects": effects,
            "no_effect": no_effect,
        }
        return data, notices

    def _card(self, item, category, notices):
        card = {"name": item.ko, "category": category, "icon": item.icon}
        entry = self._effect_for(item.english)
        tiers = (entry or {}).get("tiers") or []
        if not tiers or (entry or {}).get("source") == "MISSING":
            card["pending"] = True
            card["tiers"] = []
            notices.append("세트 효과 데이터 없음: **%s** — 카드가 비어 나갑니다" % item.ko)
        else:
            card["tiers"] = tiers
        return card
