# -*- coding: utf-8 -*-
"""디스코드 REST만 쓴다. 상시 연결(Gateway)은 하지 않는다.

깨어나서 채널 최근 글을 훑고, 새 확전 메시지가 있으면 이미지를 올리고 끝낸다.
그래서 컴퓨터를 켜둘 필요가 없고, 봇이 꺼져 있던 동안 올라온 글도 잡힌다.
"""
import json
import os

import requests

API = "https://discord.com/api/v10"
TIMEOUT = 20


class DiscordError(RuntimeError):
    pass


class Discord:
    def __init__(self, token=None, channel_id=None):
        self.token = token or os.environ.get("DISCORD_TOKEN") or ""
        self.channel_id = str(channel_id or os.environ.get("DISCORD_CHANNEL_ID") or "")
        if not self.token:
            raise DiscordError("DISCORD_TOKEN이 없습니다")
        if not self.channel_id:
            raise DiscordError("DISCORD_CHANNEL_ID가 없습니다")
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": "Bot " + self.token,
            "User-Agent": "DivisionEscalationBot/13 (+github actions)",
        })

    def _get(self, path, **kw):
        r = self.s.get(API + path, timeout=TIMEOUT, **kw)
        if r.status_code >= 400:
            raise DiscordError("GET %s -> %s %s" % (path, r.status_code, r.text[:300]))
        return r.json()

    def me(self):
        return self._get("/users/@me")

    def recent(self, limit=30):
        return self._get("/channels/%s/messages" % self.channel_id,
                         params={"limit": limit})

    # ---------- 읽기 ----------
    @staticmethod
    def message_text(msg):
        """본문과 임베드를 한 덩어리로 합친다. 원문이 임베드에만 있는 경우가 있다."""
        parts = []
        if msg.get("content"):
            parts.append(msg["content"])
        for emb in msg.get("embeds") or []:
            for key in ("title", "description"):
                if emb.get(key):
                    parts.append(emb[key])
            for fld in emb.get("fields") or []:
                if fld.get("name"):
                    parts.append(fld["name"])
                if fld.get("value"):
                    parts.append(fld["value"])
        return "\n".join(parts)

    @staticmethod
    def is_from(msg, bot_name):
        a = msg.get("author") or {}
        if not a.get("bot"):
            return False
        name = (a.get("username") or "").lower()
        globl = (a.get("global_name") or "").lower()
        want = bot_name.lower()
        return want in name or want in globl

    def find_source(self, bot_name, limit=30):
        """대상 봇이 올린 가장 최근 글을 돌려준다. 없으면 None."""
        for msg in self.recent(limit):
            if self.is_from(msg, bot_name):
                return msg
        return None

    def already_posted(self, marker, limit=30, my_id=None):
        """내가 이미 이 날짜로 올렸는지 확인한다.

        첨부 파일 이름에 날짜를 박아두고 그것을 표식으로 쓴다.
        따로 상태 파일을 두지 않아도 되고, 실행 환경이 매번 새로 시작해도 안전하다.
        """
        my_id = my_id or self.me()["id"]
        for msg in self.recent(limit):
            if (msg.get("author") or {}).get("id") != my_id:
                continue
            for att in msg.get("attachments") or []:
                if marker in (att.get("filename") or ""):
                    return True
            if marker in (msg.get("content") or ""):
                return True
        return False

    # ---------- 쓰기 ----------
    def post_image(self, png_bytes, filename, content=""):
        payload = {"attachments": [{"id": 0, "filename": filename}]}
        if content:
            payload["content"] = content
        files = {
            "payload_json": (None, json.dumps(payload), "application/json"),
            "files[0]": (filename, png_bytes, "image/png"),
        }
        r = self.s.post(API + "/channels/%s/messages" % self.channel_id,
                        files=files, timeout=60)
        if r.status_code >= 400:
            raise DiscordError("전송 실패 %s %s" % (r.status_code, r.text[:300]))
        return r.json()
