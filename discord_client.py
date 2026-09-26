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

# 포럼·미디어 채널(게시판)은 메시지를 받지 않고 '새 글(스레드)' 단위로만 받는다.
FORUM_TYPES = (15, 16)
REQUIRE_TAG = 1 << 4        # 게시판 설정의 '글 쓸 때 태그 필수'


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
        self._info = None
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

    def info(self):
        if self._info is None:
            self._info = self._get("/channels/%s" % self.channel_id)
        return self._info

    def name(self):
        return self.info().get("name") or self.channel_id

    def is_forum(self):
        return self.info().get("type") in FORUM_TYPES

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

    def find_source(self, bot_name, limit=50):
        """대상 봇이 올린 가장 최근 글을 돌려준다. 없으면 None."""
        for msg in self.recent(limit):
            if self.is_from(msg, bot_name):
                return msg
        return None

    def already_posted(self, marker, limit=100, my_id=None):
        """내가 이미 이 날짜로 올렸는지 확인한다.

        첨부 파일 이름에 날짜를 박아두고 그것을 표식으로 쓴다.
        따로 상태 파일을 두지 않아도 되고, 실행 환경이 매번 새로 시작해도 안전하다.
        """
        my_id = my_id or self.me()["id"]
        if self.is_forum():
            return self._posted_in_forum(marker, my_id)
        for msg in self.recent(limit):
            if (msg.get("author") or {}).get("id") != my_id:
                continue
            for att in msg.get("attachments") or []:
                if marker in (att.get("filename") or ""):
                    return True
            if marker in (msg.get("content") or ""):
                return True
        return False

    def _forum_threads(self):
        """이 게시판의 최근 글. 열린 글과 보관된 글을 함께 본다."""
        out = []
        gid = self.info().get("guild_id")
        if gid:
            act = self._get("/guilds/%s/threads/active" % gid)
            out += [t for t in act.get("threads", [])
                    if t.get("parent_id") == self.channel_id]
        try:
            # 보관된 글은 '메시지 기록 보기' 권한이 있어야 보인다. 없으면 열린 글만 본다.
            arc = self._get("/channels/%s/threads/archived/public" % self.channel_id,
                            params={"limit": 25})
            out += arc.get("threads", [])
        except DiscordError:
            pass
        return out

    def _posted_in_forum(self, marker, my_id):
        """게시판은 글 제목에 날짜가 들어 있다. 같은 날짜의 내 글이 있으면
        첫 메시지의 첨부 파일 이름으로 내용까지 같은지 본다. 원문 봇이 정정해서
        다시 올린 날은 해시가 달라지므로 새 글로 나간다."""
        day = marker.rsplit("_", 1)[0]
        for t in self._forum_threads():
            if t.get("owner_id") != my_id or day not in (t.get("name") or ""):
                continue
            try:
                # 게시판 글은 스레드 ID 와 첫 메시지 ID 가 같다
                first = self._get("/channels/%s/messages/%s" % (t["id"], t["id"]))
            except DiscordError:
                return True     # 확인이 안 되면 올린 것으로 친다. 두 번 나가는 것보다 낫다.
            for att in first.get("attachments") or []:
                if marker in (att.get("filename") or ""):
                    return True
        return False

    # ---------- 쓰기 ----------
    def post_image(self, png_bytes, filename, content="", title=None):
        if self.is_forum():
            return self._post_forum(png_bytes, filename, content, title or filename)
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

    def _post_forum(self, png_bytes, filename, content, title):
        """게시판에는 메시지를 보낼 수 없어서 새 글을 연다. 그림이 첫 메시지가 된다."""
        message = {"attachments": [{"id": 0, "filename": filename}]}
        if content:
            message["content"] = content
        payload = {"name": title[:100], "message": message}
        tags = self._tags_for_post()
        if tags:
            payload["applied_tags"] = tags
        files = {
            "payload_json": (None, json.dumps(payload), "application/json"),
            "files[0]": (filename, png_bytes, "image/png"),
        }
        r = self.s.post(API + "/channels/%s/threads" % self.channel_id,
                        files=files, timeout=60)
        if r.status_code >= 400:
            raise DiscordError("게시판 글쓰기 실패 %s %s" % (r.status_code, r.text[:300]))
        return r.json()

    def _tags_for_post(self):
        """태그는 DISCORD_FORUM_TAG 로 이름을 받아 붙인다. 태그가 필수인
        게시판인데 지정이 없으면 아무거나 고르지 않고 멈춘다."""
        info = self.info()
        avail = info.get("available_tags") or []
        names = ", ".join(t.get("name", "") for t in avail) or "(없음)"
        want = (os.environ.get("DISCORD_FORUM_TAG") or "").strip()
        if want:
            hit = [t["id"] for t in avail if t.get("name") == want]
            if not hit:
                raise DiscordError("게시판에 '%s' 태그가 없습니다. 있는 태그: %s"
                                   % (want, names))
            return hit[:1]
        if (info.get("flags") or 0) & REQUIRE_TAG:
            raise DiscordError("이 게시판은 글에 태그가 필수입니다. DISCORD_FORUM_TAG 에 "
                               "태그 이름을 넣어 주세요. 있는 태그: %s" % names)
        return []
