# -*- coding: utf-8 -*-
"""확전 번역봇 v13 — 진입점.

  python bot.py                    한 번 확인하고 끝낸다
  python bot.py --watch 240        새 글이 올 때까지 최대 240분 지켜본다
  python bot.py --dry-run          읽되 전송하지 않는다
  python bot.py --file msg.txt     파일로 그림만 만든다 (오프라인)
  python bot.py --force            같은 내용이어도 다시 보낸다
  python bot.py --channel 123,456  환경변수 대신 채널을 직접 지정

환경변수
  DISCORD_TOKEN        봇 토큰                        (필수)
  DISCORD_CHANNEL_ID   채널 ID. 쉼표로 여러 개 가능      (필수)
  SOURCE_BOT_NAME      원문 봇 이름                    (기본: Daily Escalation Target Loot)
  DEEPL_API_KEY        사전에 없을 때만 쓰는 키          (선택)

GitHub 예약 실행은 지정한 시각을 지키지 않는다. 실측해 보니 하루 한두 번,
슬롯과 무관한 시각에 돌았다. 그래서 "깨어난 김에 끝내는" 방식으로는 원문
게시 시각을 맞출 수가 없다. --watch 를 주면 깨어난 뒤 새 글이 올 때까지
자리를 지키므로, 언제 깨어나든 그날 것을 잡는다.
"""
import argparse
import datetime as _dt
import hashlib
import io
import os
import re
import sys
import time

import config as cfg
import parser as msg_parser
import pipeline as pl
import renderer

DEFAULT_SOURCE = "Daily Escalation Target Loot"


def log(msg):
    print(msg, flush=True)


def stamp():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%H:%M")


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


def save_local(name, img, suffix=""):
    cfg.OUT.mkdir(parents=True, exist_ok=True)
    path = cfg.OUT / ("escalation_%s%s.png" % (name, suffix))
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
    out = save_local(data["date"], img)
    log("[완료] %s  (%d x %d)" % (out, img.size[0], img.size[1]))
    for n in notices:
        log("  · " + n)
    return 0


def run_one_channel(cid, pipe, source_name, dry_run, force, quiet=False):
    """채널 하나 처리. (종료코드, 전송했는지) 를 돌려준다."""
    import discord_client as dc

    api = dc.Discord(channel_id=cid)
    name = api._get("/channels/%s" % cid).get("name")

    msg = api.find_source(source_name)
    if not msg:
        if not quiet:
            log("  [#%s] 원문 봇의 메시지를 찾지 못했습니다" % name)
        return 3, False

    parsed = msg_parser.parse(api.message_text(msg))
    if not parsed:
        if not quiet:
            log("  [#%s] 확전 형식이 아닙니다" % name)
        return 4, False

    marker = "%s_%s" % (parsed["date"], content_key(parsed))
    if not force and api.already_posted(marker):
        if not quiet:
            log("  [#%s] %s — 이미 올린 내용" % (name, marker))
        return 0, False

    log("  [#%s] %s / 임무 %d개 / 벤더 %d개 — 새 내용"
        % (name, marker, len(parsed["missions"]), len(parsed["vendor"])))

    posted_at = msg.get("timestamp")
    when = (_dt.datetime.fromisoformat(posted_at) if posted_at
            else _dt.datetime.now(_dt.timezone.utc))
    data, notices = pipe.build(parsed, when)

    img, buf = render_png(data)
    save_local(marker, img, "_" + cid[-4:])
    for n in notices:
        log("    [알림] " + n)

    if dry_run:
        log("    [건너뜀] --dry-run 이라 전송하지 않습니다")
        return 0, False

    api.post_image(buf.getvalue(), "escalation_%s.png" % marker)
    log("    [전송] 완료")
    return 0, True


def sweep(ids, pipe, source_name, dry_run, force, quiet=False):
    """모든 채널을 한 바퀴 돈다. (채널별 종료코드, 전송한 채널 집합)"""
    rcs, posted = {}, set()
    for cid in ids:
        try:
            rc, did = run_one_channel(cid, pipe, source_name, dry_run, force, quiet)
        except Exception as exc:
            # 한 채널이 막혀도 나머지는 계속 처리한다
            log("  [오류] %s: %s" % (type(exc).__name__, exc))
            rc, did = 5, False
        rcs[cid] = rc
        if did:
            posted.add(cid)
    return rcs, posted


def run_discord(dry_run=False, force=False, explicit=None,
                watch=0, interval=300):
    ids = channel_ids(explicit)
    if not ids:
        log("[오류] DISCORD_CHANNEL_ID 가 없습니다")
        return 1

    source_name = os.environ.get("SOURCE_BOT_NAME") or DEFAULT_SOURCE
    pipe = pl.Pipeline()
    log("[감시] '%s' / 채널 %d곳%s"
        % (source_name, len(ids),
           (" / 최대 %d분 지켜봄" % watch) if watch else ""))

    # 채널별로 '마지막에 본 상태'만 남긴다. 다섯 시간을 지켜보다 보면 통신이
    # 한 번쯤 끊기는데, 그 한 번을 끝까지 들고 가면 제대로 게시하고도 실행이
    # 실패로 남는다. 그러면 진짜 고장과 구분할 수가 없다.
    state, done = sweep(ids, pipe, source_name, dry_run, force)

    if watch and len(done) < len(ids):
        deadline = time.monotonic() + watch * 60
        rounds = 0
        while time.monotonic() < deadline and len(done) < len(ids):
            time.sleep(min(interval, max(1, deadline - time.monotonic())))
            rounds += 1
            left = [c for c in ids if c not in done]
            rcs, got = sweep(left, pipe, source_name, dry_run, force, quiet=True)
            state.update(rcs)
            done |= got
            if rounds % 12 == 0 and not got:
                log("  [%s UTC] 아직 새 글 없음 — %d곳 대기 중" % (stamp(), len(left)))
        if len(done) < len(ids):
            log("[종료] 지켜보기 시간이 끝났습니다 (%d/%d곳 전송)"
                % (len(done), len(ids)))

    worst = max(state.values()) if state else 0
    if worst:
        # 조용히 실패하지 않는다. 지켜보는 동안은 로그를 줄여두므로
        # 끝에 한 번은 어느 채널이 왜 걸렸는지 남긴다.
        log("[결과] 마지막 확인에서 정상이 아닌 채널 %d곳: %s"
            % (sum(1 for rc in state.values() if rc),
               ", ".join("...%s(rc=%d)" % (c[-4:], rc)
                         for c, rc in state.items() if rc)))

    for eng, ko in pipe.tr.flush_pending():
        log("[사전 추가] %s -> %s  (needs_review 에 올림)" % (eng, ko))
    return worst


def main(argv=None):
    ap = argparse.ArgumentParser(description="확전 번역봇 v13")
    ap.add_argument("--dry-run", action="store_true", help="읽되 전송하지 않음")
    ap.add_argument("--file", help="디스코드 대신 파일에서 읽음")
    ap.add_argument("--force", action="store_true", help="같은 내용이어도 다시 전송")
    ap.add_argument("--channel", help="채널 ID. 쉼표로 여러 개")
    ap.add_argument("--watch", type=int, default=0, metavar="분",
                    help="새 글이 올 때까지 지켜볼 시간 (0이면 한 번만)")
    ap.add_argument("--interval", type=int, default=300, metavar="초",
                    help="지켜볼 때 확인 간격")
    args = ap.parse_args(argv)

    try:
        if args.file:
            return run_offline(args.file)
        return run_discord(dry_run=args.dry_run, force=args.force,
                           explicit=args.channel, watch=args.watch,
                           interval=args.interval)
    except KeyboardInterrupt:
        log("[중단] 사용자 중지")
        return 130
    except Exception as exc:
        log("[오류] %s: %s" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
