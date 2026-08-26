# -*- coding: utf-8 -*-
"""확전 번역봇 v13 — 레이아웃 상수와 UI 문구.

수치와 색은 전부 여기 모아둔다. 렌더러는 여기 값만 읽는다.
인게임 표기가 바뀌면 LABELS만 고치면 되고 코드는 건드리지 않는다.
"""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent


def pathlib_out():
    """결과 PNG를 둘 곳. 저장소 안이 기본이라 CI에서도 그대로 쓴다."""
    return Path(os.environ.get("ESCALATION_OUT") or (BASE / "out"))

DATA = BASE / "data"
ICONS = DATA / "icons"
OUT = pathlib_out()

# ---------- 폰트 ----------
# 로컬(윈도우)은 맑은 고딕, 배포 환경에서는 data/fonts 안에 번들한 폰트를 쓴다.
FONT_CANDIDATES = {
    "regular": [DATA / "fonts" / "Pretendard-Regular.ttf", Path("C:/Windows/Fonts/malgun.ttf")],
    "bold":    [DATA / "fonts" / "Pretendard-Bold.ttf",    Path("C:/Windows/Fonts/malgunbd.ttf")],
}

# ---------- 캔버스 ----------
WIDTH      = 1080
RAIL_W     = 8
PAD_X      = 36
PAD_TOP    = 28
PAD_BOTTOM = 20
SECTION_GAP = 28

# ---------- 색 ----------
C = {
    "ground":  (10, 10, 11),
    "band":    (16, 18, 21),
    "row_a":   (14, 16, 19),
    "row_b":   (20, 23, 26),
    "card":    (16, 19, 23),
    "rule":    (35, 40, 45),
    "hair":    (25, 29, 33),
    "text":    (237, 239, 241),
    "white":   (255, 255, 255),
    "muted":   (138, 144, 153),
    "dim":     (90, 96, 104),
    "amber":   (255, 122, 0),
    "amber2":  (255, 162, 77),
    "rail_off": (122, 58, 0),
    "cat":     (115, 124, 132),
    "body":    (191, 198, 204),
    "body2":   (153, 162, 170),
    "foot":    (71, 77, 84),
    "made":    (110, 118, 126),
    "none_tx": (90, 96, 104),
    "none_ln": (46, 53, 59),
    "cap_bg":  (28, 24, 22),   # 4+ 개 특성 줄 배경 (주황 5% 를 미리 합성한 값)
}

# 카테고리별 아이콘 색. 아이콘 PNG 자체가 이미 이 색으로 칠해져 있다.
CATEGORY_COLOR = {
    "보호장구 세트": (100, 240, 131),
    "브랜드 세트":   (255, 192, 46),
    "보호장구":      (237, 241, 244),
    "무기":          (237, 241, 244),
}

# ---------- 글자 크기 ----------
S = {
    "title": 35, "date": 16,
    "clock_lbl": 11, "clock_zone": 12, "clock_kst": 24, "clock_utc": 20,
    "sec_title": 20,
    "th": 11, "td": 20, "num": 15, "cat": 14,
    "card_name": 19, "card_cat": 13, "tier": 14, "body": 15, "talent": 16,
    "none": 13, "foot": 13,
}

# ---------- 자간 (px) ----------
LS = {"sec_title": 1.1, "th": 1.4, "clock_lbl": 1.8, "clock_zone": 1.7, "foot": 1.0}

# ---------- 표 열 너비 ----------
COL_NUM     = 54
COL_MISSION = 400
COL_LOOT    = 376
COL_CAT     = 170

ROW_PAD_Y   = 10
ROW_PAD_X   = 16
ICON_ROW    = 44
ICON_GAP    = 13

# ---------- 세트 효과 카드 ----------
CARD_GAP     = 13
CARD_CHAMFER = 12
CARD_HEAD_PY = 10
CARD_PAD_X   = 15
CARD_ROW_PY  = 9
ICON_CARD    = 46
TIER_W       = 54
TIER_GAP     = 15
LINE_H       = 1.55
PARA_GAP     = 7

HEAD_CHAMFER = 18
HEAD_PAD_X   = 24
HEAD_PAD_Y   = 20

# ---------- UI 문구 ----------
LABELS = {
    "title":        "일일 확전 지정 전리품",
    "updated":      "업데이트",
    "sec_missions": "임무",
    "sec_vendor":   "확전 보급 판매상",
    "sec_effects":  "세트 효과",
    "th_no":        "#",
    "th_mission":   "임무",
    "th_loot":      "지정 전리품",
    "th_category":  "카테고리",
    "th_type":      "타입",
    "th_lineup":    "라인업",
    "tier_suffix":  "+ 개",
    "no_effect":    "{names}{particle} 세트 효과가 없습니다",
    "pending":      "효과 데이터 준비 중",
    "auto_mark":    "자동 번역",
    "source":       "데이터 출처 · ProtoTrack.gg",
    "credit":       "번역봇 제작 · subak77",
}
