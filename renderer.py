# -*- coding: utf-8 -*-
"""확전 정보를 PNG 한 장으로 그린다.

카드 높이가 글 길이에 따라 달라지므로 두 번 훑는다.
먼저 재서 캔버스 높이를 구하고, 그 다음 실제로 그린다.
"""
import datetime as _dt
from PIL import Image, ImageDraw

import config as cfg
import textkit as tk

WEEKDAY = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

CONTENT_W = cfg.WIDTH - cfg.RAIL_W - cfg.PAD_X * 2
CARD_W = (CONTENT_W - cfg.CARD_GAP) // 2
CARD_TEXT_W = CARD_W - cfg.CARD_PAD_X * 2 - cfg.TIER_W - cfg.TIER_GAP
BODY_LH = round(cfg.S["body"] * cfg.LINE_H)
TIER_SUFFIX = cfg.LABELS["tier_suffix"]


class Renderer:
    def __init__(self):
        f = cfg.FONT_CANDIDATES
        self.fr = {k: tk.load_font(f["regular"], v) for k, v in cfg.S.items()}
        self.fb = {k: tk.load_font(f["bold"], v) for k, v in cfg.S.items()}
        self._probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        self._icons = {}
        self._rowcache = {}

    # ---------- 아이콘 ----------
    def icon(self, rel, size):
        key = (rel, size)
        if key in self._icons:
            return self._icons[key]
        path = cfg.ICONS / rel
        if not path.exists():
            self._icons[key] = None
            return None
        im = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        self._icons[key] = im
        return im

    # ---------- 재기 ----------
    def _card_rows(self, eff):
        """카드 한 장의 각 줄을 (종류, 높이, 내용)으로 펼친다."""
        cached = self._rowcache.get(id(eff))
        if cached is not None:
            return cached
        rows = []
        if eff.get("pending"):
            rows.append(("pending", cfg.CARD_ROW_PY * 2 + BODY_LH, None))
            return rows
        for t in eff["tiers"]:
            if t.get("talent"):
                h = cfg.CARD_ROW_PY * 2 + round(cfg.S["talent"] * 1.3) + 3
                paras = []
                for i, p in enumerate(t.get("paragraphs", [])):
                    segs = tk.parse_rich(tk.emphasize(p))
                    lines = tk.wrap_rich(self._probe, segs, self.fr["body"],
                                         self.fb["body"], CARD_TEXT_W)
                    paras.append(lines)
                    h += len(lines) * BODY_LH + (cfg.PARA_GAP if i else 0)
                rows.append(("talent", h, (t["talent"], paras)))
            else:
                segs = tk.parse_rich(tk.emphasize(t["text"]))
                lines = tk.wrap_rich(self._probe, segs, self.fr["body"],
                                     self.fb["body"], CARD_TEXT_W)
                rows.append(("tier", cfg.CARD_ROW_PY * 2 + len(lines) * BODY_LH,
                             (t["n"], lines)))
        self._rowcache[id(eff)] = rows
        return rows

    def _card_height(self, eff):
        head = cfg.CARD_HEAD_PY * 2 + max(cfg.ICON_CARD,
                                          tk.line_height(self.fb["card_name"]))
        return head + sum(r[1] for r in self._card_rows(eff))

    def _split_columns(self, effects):
        """카드를 두 열에 나눈다. 매번 낮은 쪽에 얹어서 빈 구멍을 없앤다."""
        cols = ([], [])
        heights = [0, 0]
        for eff in effects:
            h = self._card_height(eff)
            i = 0 if heights[0] <= heights[1] else 1
            if cols[i]:
                heights[i] += cfg.CARD_GAP
            cols[i].append((eff, h))
            heights[i] += h
        return cols, heights

    def _grid_height(self, effects):
        _, heights = self._split_columns(effects)
        return max(heights) if effects else 0

    def _section_head_h(self):
        return 30

    def _table_h(self, rows):
        th = 11 * 2 + tk.line_height(self.fr["th"])
        return th + len(rows) * (cfg.ROW_PAD_Y * 2 + cfg.ICON_ROW)

    def _header_h(self):
        left = (tk.line_height(self.fb["title"]) + 6
                + tk.line_height(self.fr["date"]))
        right = (tk.line_height(self.fr["clock_lbl"]) + 8
                 + tk.line_height(self.fr["clock_kst"]) + 3
                 + tk.line_height(self.fr["clock_utc"]))
        return max(left, right) + cfg.HEAD_PAD_Y * 2

    def measure(self, data):
        h = cfg.PAD_TOP + self._header_h() + cfg.SECTION_GAP
        h += self._section_head_h() + self._table_h(data["missions"]) + cfg.SECTION_GAP
        h += self._section_head_h() + self._table_h(data["vendor"]) + cfg.SECTION_GAP
        h += self._section_head_h() + 15 + self._grid_height(data["effects"])
        if data.get("no_effect"):
            h += 13 + tk.line_height(self.fr["none"])
        h += 15 + 1 + max(tk.line_height(self.fr["foot"]), 14) + cfg.PAD_BOTTOM
        return h

    # ---------- 그리기 ----------
    def render(self, data):
        H = self.measure(data)
        img = Image.new("RGB", (cfg.WIDTH, H), cfg.C["ground"])
        d = ImageDraw.Draw(img)
        self._rail(d, H)

        x0 = cfg.RAIL_W + cfg.PAD_X
        y = cfg.PAD_TOP
        y = self._header(img, d, x0, y, data)
        y += cfg.SECTION_GAP

        y = self._section(d, x0, y, cfg.LABELS["sec_missions"])
        y = self._table(img, d, x0, y, data["missions"],
                        (cfg.LABELS["th_mission"], cfg.LABELS["th_loot"]), "mission")
        y += cfg.SECTION_GAP

        y = self._section(d, x0, y, cfg.LABELS["sec_vendor"])
        y = self._table(img, d, x0, y, data["vendor"],
                        (cfg.LABELS["th_type"], cfg.LABELS["th_lineup"]), "type")
        y += cfg.SECTION_GAP

        y = self._section(d, x0, y, cfg.LABELS["sec_effects"])
        y += 15
        y = self._cards(img, d, x0, y, data["effects"])
        if data.get("no_effect"):
            y = self._none_note(d, x0, y, data["no_effect"])

        self._footer(d, x0, H)
        return img

    def _rail(self, d, H):
        """주황 눈금 레일. 캔버스 끝에서 잘려도 되게 매 칸마다 확인한다."""
        y = 0
        while y < H:
            for span, col in ((21, "amber"), (3, "rail_off")):
                if y >= H:
                    break
                d.rectangle([0, y, cfg.RAIL_W - 1, min(y + span, H - 1)],
                            fill=cfg.C[col])
                y += span + 1

    def _header(self, img, d, x0, y, data):
        h = self._header_h()
        box = (x0, y, x0 + CONTENT_W, y + h)
        tk.chamfer_rect(d, box, cfg.HEAD_CHAMFER, fill=cfg.C["band"],
                        outline=cfg.C["rule"])

        tx = x0 + cfg.HEAD_PAD_X
        ty = y + cfg.HEAD_PAD_Y
        title_lh = tk.line_height(self.fb["title"])
        d.text((tx, ty + title_lh // 2), cfg.LABELS["title"],
               font=self.fb["title"], fill=cfg.C["white"], anchor="lm")
        dt = _dt.date.fromisoformat(data["date"])
        date_s = "%d년 %d월 %d일 %s" % (dt.year, dt.month, dt.day,
                                     WEEKDAY[dt.weekday()])
        dy = ty + title_lh + 6 + tk.line_height(self.fr["date"]) // 2
        d.text((tx, dy), date_s, font=self.fr["date"], fill=cfg.C["muted"],
               anchor="lm")

        rx = x0 + CONTENT_W - cfg.HEAD_PAD_X
        cy = ty + tk.line_height(self.fr["clock_lbl"]) // 2
        lbl = cfg.LABELS["updated"]
        w = tk.width_of(d, lbl, self.fr["clock_lbl"], cfg.LS["clock_lbl"])
        tk.draw_ls(d, (rx - w, cy), lbl, self.fr["clock_lbl"], cfg.C["dim"],
                   cfg.LS["clock_lbl"])

        cy = (ty + tk.line_height(self.fr["clock_lbl"]) + 8
              + tk.line_height(self.fr["clock_kst"]) // 2)
        self._clock_row(d, rx, cy, "KST", data["kst"], self.fr["clock_kst"],
                        cfg.C["amber"], cfg.C["amber2"])
        cy += (tk.line_height(self.fr["clock_kst"]) // 2 + 3
               + tk.line_height(self.fr["clock_utc"]) // 2)
        self._clock_row(d, rx, cy, "UTC", data["utc"], self.fr["clock_utc"],
                        cfg.C["dim"], cfg.C["muted"])
        return y + h

    def _clock_row(self, d, rx, cy, zone, value, font, zone_col, val_col):
        vw = d.textlength(value, font=font)
        d.text((rx, cy), value, font=font, fill=val_col, anchor="rm")
        zf = self.fr["clock_zone"]
        zw = tk.width_of(d, zone, zf, cfg.LS["clock_zone"])
        tk.draw_ls(d, (rx - vw - 12 - zw, cy), zone, zf, zone_col,
                   cfg.LS["clock_zone"])

    def _section(self, d, x0, y, title):
        d.rectangle([x0, y, x0 + 3, y + 19], fill=cfg.C["amber"])
        f = self.fb["sec_title"]
        tx = x0 + 4 + 12
        w = tk.draw_ls(d, (tx, y + 10), title, f, cfg.C["white"],
                       cfg.LS["sec_title"])
        fx = tx + w + 12
        d.rectangle([fx, y + 10, x0 + CONTENT_W, y + 10], fill=cfg.C["hair"])
        d.rectangle([x0, y + 29, x0 + CONTENT_W, y + 29], fill=cfg.C["rule"])
        return y + 30

    def _cols(self, x0):
        a = x0
        b = a + cfg.COL_NUM
        c = b + cfg.COL_MISSION
        e = c + cfg.COL_LOOT
        return a, b, c, e

    def _table(self, img, d, x0, y, rows, headers, name_key):
        a, b, c, e = self._cols(x0)
        f = self.fr["th"]
        th_h = 11 * 2 + tk.line_height(f)
        cy = y + th_h // 2
        heads = ((a, cfg.LABELS["th_no"]), (b, headers[0]),
                 (c, headers[1]), (e, cfg.LABELS["th_category"]))
        for x, s in heads:
            if x == a:
                sx = x + (cfg.COL_NUM - tk.width_of(d, s, f, cfg.LS["th"])) / 2
            else:
                sx = x + cfg.ROW_PAD_X
            tk.draw_ls(d, (sx, cy), s, f, cfg.C["dim"], cfg.LS["th"])
        y += th_h

        rh = cfg.ROW_PAD_Y * 2 + cfg.ICON_ROW
        for i, r in enumerate(rows):
            bg = cfg.C["row_a"] if i % 2 == 0 else cfg.C["row_b"]
            d.rectangle([x0, y, x0 + CONTENT_W, y + rh - 1], fill=bg)
            d.rectangle([x0, y, x0 + 2, y + rh - 1], fill=cfg.C["hair"])
            cy = y + rh // 2

            num = str(i + 1)
            nw = d.textlength(num, font=self.fr["num"])
            d.text((a + (cfg.COL_NUM - nw) / 2, cy), num,
                   font=self.fr["num"], fill=cfg.C["dim"], anchor="lm")
            d.text((b + cfg.ROW_PAD_X, cy), r[name_key],
                   font=self.fr["td"], fill=cfg.C["text"], anchor="lm")

            ix = c + cfg.ROW_PAD_X
            ic = self.icon(r["icon"], cfg.ICON_ROW) if r.get("icon") else None
            if ic:
                img.paste(ic, (int(ix), int(cy - cfg.ICON_ROW / 2)), ic)
            ix += cfg.ICON_ROW + cfg.ICON_GAP
            loot_col = cfg.C["muted"] if r.get("auto") else cfg.C["white"]
            d.text((ix, cy), r["loot"], font=self.fb["td"], fill=loot_col,
                   anchor="lm")
            if r.get("auto"):
                lw = d.textlength(r["loot"], font=self.fb["td"])
                d.text((ix + lw + 8, cy), "*", font=self.fb["td"],
                       fill=cfg.C["amber"], anchor="lm")

            d.text((e + cfg.ROW_PAD_X, cy), r.get("category", ""),
                   font=self.fr["cat"], fill=cfg.C["cat"], anchor="lm")
            y += rh
        return y

    def _cards(self, img, d, x0, y, effects):
        cols, heights = self._split_columns(effects)
        for j, col in enumerate(cols):
            cx = x0 + j * (CARD_W + cfg.CARD_GAP)
            cy = y
            for eff, h in col:
                self._card(img, d, cx, cy, eff, self._card_rows(eff))
                cy += h + cfg.CARD_GAP
        return y + (max(heights) if effects else 0)

    def _card(self, img, d, x, y, eff, rows):
        h = self._card_height(eff)
        box = (x, y, x + CARD_W, y + h)
        tk.chamfer_rect(d, box, cfg.CARD_CHAMFER, fill=cfg.C["card"])

        head_h = cfg.CARD_HEAD_PY * 2 + max(cfg.ICON_CARD,
                                            tk.line_height(self.fb["card_name"]))
        d.rectangle([x + 1, y + 1, x + CARD_W - 1, y + head_h],
                    fill=cfg.C["row_b"])
        tk.chamfer_rect(d, box, cfg.CARD_CHAMFER, outline=cfg.C["rule"])
        d.rectangle([x, y + head_h, x + CARD_W, y + head_h], fill=cfg.C["rule"])

        cy = y + head_h // 2
        ix = x + cfg.CARD_PAD_X
        ic = self.icon(eff["icon"], cfg.ICON_CARD) if eff.get("icon") else None
        if ic:
            img.paste(ic, (int(ix), int(cy - cfg.ICON_CARD / 2)), ic)
        ix += cfg.ICON_CARD + 12
        d.text((ix, cy), eff["name"], font=self.fb["card_name"],
               fill=cfg.C["white"], anchor="lm")
        cat = eff.get("category", "")
        if cat:
            cw = d.textlength(cat, font=self.fr["card_cat"])
            d.text((x + CARD_W - cfg.CARD_PAD_X - cw, cy), cat,
                   font=self.fr["card_cat"], fill=cfg.C["cat"], anchor="lm")

        ry = y + head_h + 1
        tx = x + cfg.CARD_PAD_X + cfg.TIER_W + cfg.TIER_GAP
        for k, (kind, rh, payload) in enumerate(rows):
            if kind == "talent":
                d.rectangle([x + 1, ry, x + CARD_W - 1, ry + rh - 1],
                            fill=cfg.C["cap_bg"])
            if k:
                d.rectangle([x + 1, ry, x + CARD_W - 1, ry], fill=cfg.C["hair"])

            ty = ry + cfg.CARD_ROW_PY
            if kind == "pending":
                d.text((x + cfg.CARD_PAD_X, ty + BODY_LH // 2),
                       cfg.LABELS["pending"], font=self.fr["body"],
                       fill=cfg.C["dim"], anchor="lm")
                ry += rh
                continue

            n = payload[0] if kind == "tier" else 4
            tier_s = str(n) + TIER_SUFFIX
            tw = d.textlength(tier_s, font=self.fr["tier"])
            tier_col = cfg.C["amber"] if kind == "talent" else cfg.C["dim"]
            d.text((x + cfg.CARD_PAD_X + cfg.TIER_W - tw, ty + BODY_LH // 2),
                   tier_s, font=self.fr["tier"], fill=tier_col, anchor="lm")

            if kind == "tier":
                for line in payload[1]:
                    tk.draw_rich_line(d, (tx, ty + BODY_LH // 2), line,
                                      self.fr["body"], self.fb["body"],
                                      cfg.C["body"], cfg.C["white"])
                    ty += BODY_LH
            else:
                talent, paras = payload
                tlh = round(cfg.S["talent"] * 1.3)
                d.text((tx, ty + tlh // 2), talent, font=self.fb["talent"],
                       fill=cfg.C["amber2"], anchor="lm")
                ty += tlh + 3
                for pi, lines in enumerate(paras):
                    if pi:
                        ty += cfg.PARA_GAP
                    col = cfg.C["body"] if pi == 0 else cfg.C["body2"]
                    for line in lines:
                        tk.draw_rich_line(d, (tx, ty + BODY_LH // 2), line,
                                          self.fr["body"], self.fb["body"],
                                          col, cfg.C["white"])
                        ty += BODY_LH
            ry += rh

    def _none_note(self, d, x0, y, names):
        y += 13
        f = self.fr["none"]
        cy = y + tk.line_height(f) // 2
        d.rectangle([x0, cy, x0 + 13, cy], fill=cfg.C["none_ln"])
        joined = " · ".join(names)
        particle = "은" if _has_final(names[-1]) else "는"
        s = cfg.LABELS["no_effect"].format(names=joined, particle=particle)
        d.text((x0 + 23, cy), s, font=f, fill=cfg.C["none_tx"], anchor="lm")
        return y + tk.line_height(f)

    def _footer(self, d, x0, H):
        y = H - cfg.PAD_BOTTOM - max(tk.line_height(self.fr["foot"]), 14)
        d.rectangle([x0, y - 15, x0 + CONTENT_W, y - 15], fill=cfg.C["hair"])
        f = self.fr["foot"]
        cy = y + tk.line_height(f) // 2
        tk.draw_ls(d, (x0, cy), cfg.LABELS["source"], f, cfg.C["foot"],
                   cfg.LS["foot"])
        credit = cfg.LABELS["credit"]
        head, sep, who = credit.rpartition("· ")
        head = head + sep
        wh = tk.width_of(d, head, f, cfg.LS["foot"])
        ww = tk.width_of(d, who, f, cfg.LS["foot"])
        sx = x0 + CONTENT_W - wh - ww
        tk.draw_ls(d, (sx, cy), head, f, cfg.C["made"], cfg.LS["foot"])
        tk.draw_ls(d, (sx + wh, cy), who, f, cfg.C["amber"], cfg.LS["foot"])


def _has_final(word):
    """받침이 있으면 True. '권총집은' / '소총는' 을 가르기 위한 것."""
    for ch in reversed(word):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 != 0
    return False


def render(data):
    return Renderer().render(data)
