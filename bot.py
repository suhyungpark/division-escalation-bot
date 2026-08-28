# -*- coding: utf-8 -*-
"""확전 번역봇 v13 — 진입점.

한 번 깨어나서 할 일만 하고 끝낸다. 상주하지 않는다.

  python bot.py                    채널을 보고 새 글이 있으면 올린다
  python bot.py --dry-run          채널은 읽되 올리지는 않는다
  python bot.py --file msg.txt     파일을 읽어서 그림만 만든다 (오프라인)
  python bot.py --force            이미 올린 날짜여도 다시 올린다
  python bot.py --channel 123,456  환경변수 대신 채널을 직접 지정

환경변수
  DISCORD_TOKEN        봇 토큰                        (필수)
  DISCORD_CHANNEL_ID   채널 ID. 쉼표로 여러 개 가능      (필수)
  SOURCE_BOT_NAME      원문 봇 이름                    (기본: Daily Escalation Target Loot)
  DEEPL_API_KEY        사전에 없을 때만 쓰는 키          (선택)

채널마다 원문 글도 따로, 중복 확인도 따로 한다. 서버가 달라도 상관없다.
한 채널이 실패해도 나머지는 계속 처리한다.
"""
import argparse
import datetime as _dt
import hashlib
import io
import os
import re
import sys

import config as cfg
import parser as msg_parser
import pipeline as pl
import renderer

DEFAULT_SOURCE = "Daily Escalation Target Loot"


def log(msg):
    print(msg, flush=True)


def channel_ids(explicit=None):
    raw = explicit or os.environ.get("DISCORD_CHANNEL_ID") or ""
    return [c for c in re.split(r"[,\s]+", raw.strip()) if c]


def content_key(parsed):
    """같은 날짜라도 내용이 바뀌면 달라지는 표식.

    원문 봇이 하루치를 정정해서 다시 올리는 일이 있다. 날짜만 보고
    중복을 판단하면 그 정정본을 영영 못 내보낸다. 파싱된 항목만으로
    해시를 만들어서, 이모지나 서식이 바뀐 정도로는 흔들리지 않게 한다.
    """
    parts = [parsed["date"]]
    for r in parsed["missions"]:
        parts.append("%s>%s" % (r["mission_en"], r["loot_en"]))
    for r in parsed.get("vendor", []):
        parts.append("%s>%s" % (r["type_en"], r["loot_en"]))
    raw = "|".join(parts).lower().replace(" ", "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]


def render_png(data):
    img = renderer.render(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return img, buf


def save_local(img, date, suffix=""):
    cfg.OUT.mkdir(parents=True, exist_ok=True)
    path = cfg.OUT / ("escalation_%s%s.png" % (date, suffix))
    img.save(path)
    return path


def run_offline(path):
    text = open(path, encoding="utf-8").read()
    parsed = msg_parser.parse(text)
    if not parsed:
        log("[중단] 확전 메시지 형식이 아닙니다: %s" % path)
        return 2
    when = _dt.datetime.now(_dt.timezone.utc)
    data, notices = pl.Pipeline().build(parsed, when)
    img, _ = render_png(data)
    out = save_local(img, data["date"])
    log("[완료] %s  (%d x %d)" % (out, img.size[0], img.size[1]))
    for n in notices:
        log("  · " + n)
    return 0


def run_one_channel(cid, pipe, source_name, dry_run, force):
    """채널 하나를 처리한다. 0이면 정상(전송했거나 건너뛰었거나)."""
    import discord_client as dc

    api = dc.Discord(channel_id=cid)
    info = api._get("/channels/%s" % cid)
    log("[채널] #%s (%s)" % (info.get("name"), cid))

    msg = api.find_source(source_name)
    if not msg:
        log("  [중단] 최근 글에서 원문 봇의 메시지를 찾지 못했습니다")
        return 3

    parsed = msg_parser.parse(api.message_text(msg))
    if not parsed:
        log("  [중단] 찾은 메시지가 확전 형식이 아닙니다")
        return 4

    date = parsed["date"]
    marker = "%s_%s" % (date, content_key(parsed))
    log("  [감지] %s / 임무 %d개 / 벤더 %d개 / 내용 %s"
        % (date, len(parsed["missions"]), len(parsed["vendor"]), marker[-6:]))

    if not force and api.already_posted(marker):
        log("  [건너뜀] 같은 내용을 이미 올렸습니다 (%s)" % marker)
        return 0

    posted_at = msg.get("timestamp")
    when = (_dt.datetime.fromisoformat(posted_at) if posted_at
            else _dt.datetime.now(_dt.timezone.utc))
    data, notices = pipe.build(parsed, when)

    img, buf = render_png(data)
    save_local(img, marker, "_" + cid[-4:])
    for n in notices:
        log("  [알림] " + n)

    if dry_run:
        log("  [건너뜀] --dry-run 이라 전송하지 않습니다")
        return 0

    api.post_image(buf.getvalue(), "escalation_%s.png" % marker)
    log("  [전송] 완료")
    return 0


def run_discord(dry_run=False, force=False, explicit=None):
    ids = channel_ids(explicit)
    if not ids:
        log("[오류] DISCORD_CHANNEL_ID 가 없습니다")
        return 1

    source_name = os.environ.get("SOURCE_BOT_NAME") or DEFAULT_SOURCE
    log("[감시] '%s' / 채널 %d곳" % (source_name, len(ids)))

    pipe = pl.Pipeline()
    worst = 0
    for cid in ids:
        try:
            rc = run_one_channel(cid, pipe, source_name, dry_run, force)
        except Exception as exc:
            # 한 채널이 막혀도 나머지는 계속 처리한다
            log("  [오류] %s: %s" % (type(exc).__name__, exc))
            rc = 5
        worst = max(worst, rc)

    for eng, ko in pipe.tr.flush_pending():
        log("[사전 추가] %s -> %s  (needs_review 에 올림)" % (eng, ko))
    return worst


def main(argv=None):
    ap = argparse.ArgumentParser(description="확전 번역봇 v13")
    ap.add_argument("--dry-run", action="store_true", help="읽되 전송하지 않음")
    ap.add_argument("--file", help="디스코드 대신 파일에서 읽음")
    ap.add_argument("--force", action="store_true", help="이미 올린 날짜여도 다시 전송")
    ap.add_argument("--channel", help="채널 ID. 쉼표로 여러 개")
    args = ap.parse_args(argv)

    try:
        if args.file:
            return run_offline(args.file)
        return run_discord(dry_run=args.dry_run, force=args.force,
                           explicit=args.channel)
    except Exception as exc:
        log("[오류] %s: %s" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
