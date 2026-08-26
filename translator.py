# -*- coding: utf-8 -*-
"""영문 이름을 한글·카테고리·아이콘으로 바꾼다.

찾는 순서는 네 단계다.
  1. 카탈로그에서 그대로 찾기
  2. 대소문자·기호·복수형을 없앤 뒤 다시 찾기   <- Holster/Holsters 를 여기서 잡는다
  3. 편집거리로 가장 가까운 것 찾기            <- 오타와 표기 흔들림
  4. DeepL                                  <- 여기까지 와야 API를 부른다

4단계까지 간 항목은 auto=True로 표시해서 이미지에 회색+별표로 나오게 하고,
pending에 쌓아 두었다가 사전에 자동으로 적어 넣는다. 다음 실행부터는 1단계에서 걸린다.
"""
import difflib
import json
import os
import re
import unicodedata

import config as cfg

FUZZY_MIN = 0.86


def norm(s):
    s = unicodedata.normalize("NFKD", s).lower()
    s = s.replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", s)


def depluralise(n):
    return n[:-1] if len(n) > 3 and n.endswith("s") else n


class Entry:
    __slots__ = ("english", "ko", "category", "icon", "auto", "review", "how")

    def __init__(self, english, ko, category="", icon=None,
                 auto=False, review=False, how="exact"):
        self.english = english
        self.ko = ko
        self.category = category
        self.icon = icon
        self.auto = auto
        self.review = review
        self.how = how

    def flagged(self):
        """이미지에 '믿지 마세요' 표시를 할지."""
        return self.auto or self.review


class Translator:
    def __init__(self, catalog=None, deepl_key=None):
        path = catalog or (cfg.DATA / "catalog.json")
        with open(path, encoding="utf-8") as f:
            self.cat = json.load(f)
        self.items = self.cat["items"]
        self.missions = self.cat["missions"]
        self._index = {}
        for eng in self.items:
            self._index.setdefault(norm(eng), eng)
            self._index.setdefault(depluralise(norm(eng)), eng)
        self._mission_index = {}
        for eng in self.missions:
            self._mission_index.setdefault(norm(eng), eng)
        self.deepl_key = deepl_key or os.environ.get("DEEPL_API_KEY") or ""
        self.pending = []      # 이번 실행에서 기계번역한 것
        self.unknown = []      # 기계번역조차 실패한 것

    # ---------- 조회 ----------
    def _find(self, english, index):
        n = norm(english)
        if n in index:
            return index[n], "exact"
        d = depluralise(n)
        if d in index:
            return index[d], "normalised"
        near = difflib.get_close_matches(n, list(index), n=1, cutoff=FUZZY_MIN)
        if near:
            return index[near[0]], "fuzzy"
        return None, "none"

    def item(self, english):
        english = english.strip()
        key, how = self._find(english, self._index)
        if key:
            e = self.items[key]
            return Entry(english, e["ko"], e.get("category", ""), e.get("icon"),
                         auto=False, review=bool(e.get("review")), how=how)
        ko = self._deepl(english)
        if ko:
            self.pending.append((english, ko))
            return Entry(english, ko, "", None, auto=True, how="deepl")
        self.unknown.append(english)
        return Entry(english, english, "", None, auto=True, how="none")

    def mission(self, english):
        english = english.strip()
        key, how = self._find(english, self._mission_index)
        if key:
            return Entry(english, self.missions[key], how=how)
        ko = self._deepl(english)
        if ko:
            self.pending.append((english, ko))
            return Entry(english, ko, auto=True, how="deepl")
        self.unknown.append(english)
        return Entry(english, english, auto=True, how="none")

    # ---------- 기계번역 ----------
    def _deepl(self, text):
        if not self.deepl_key:
            return None
        import requests
        host = "api-free.deepl.com" if self.deepl_key.endswith(":fx") else "api.deepl.com"
        try:
            # DeepL은 본문에 키를 넣는 방식을 더 이상 받지 않는다. 헤더로 보낸다.
            r = requests.post(
                "https://%s/v2/translate" % host,
                headers={"Authorization": "DeepL-Auth-Key " + self.deepl_key},
                data={"text": text, "target_lang": "KO", "source_lang": "EN"},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()["translations"][0]["text"].strip()
        except Exception as exc:      # 번역 하나 실패로 전체를 멈추지 않는다
            print("[DeepL 실패] %s: %s" % (text, exc))
            return None

    # ---------- 사전 자동 보강 ----------
    def flush_pending(self, overrides_path=None):
        """기계번역한 것을 overrides.json에 적어 둔다.

        GitHub Actions는 실행할 때마다 새로 시작하므로, 남겨두지 않으면
        같은 항목을 매번 다시 번역하게 된다. 적어 두면 다음 실행부터는
        API를 안 부르고, needs_review에 남아 있어 나중에 손볼 목록이 된다.
        """
        if not self.pending:
            return []
        path = overrides_path or (cfg.DATA / "overrides.json")
        with open(path, encoding="utf-8") as f:
            ov = json.load(f)
        ov.setdefault("items", {})
        ov.setdefault("needs_review", [])
        added = []
        for eng, ko in self.pending:
            if eng in ov["items"]:
                continue
            ov["items"][eng] = ko
            if eng not in ov["needs_review"]:
                ov["needs_review"].append(eng)
            added.append((eng, ko))
        if added:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ov, f, ensure_ascii=False, indent=2)
        return added
