# -*- coding: utf-8 -*-
"""자료 배포(giveaway) 글의 댓글을 챙기는 로컬 도구. (쓰레드 전자책 5부 '댓글 단 사람에게 자료 보내기' 방식)

Threads API 에는 DM 이 없다. 그래서 순서는 이렇다.
  1) 이 도구가 키워드 댓글을 모아 "누구에게 어떤 DM 을 보낼지" 목록과 붙여넣을 DM 문구를 보여 준다
  2) 사람이 Threads 앱에서 DM 을 보낸다 (팔로워가 아니면 DM 이 막힐 수 있다 → 그 사람은 팔로우 안내 답글)
  3) --yes 로 다시 돌리면 DM 이 나간 사람에게 공개 답글("DM 보냈어요")을 단다. 구경하는 사람에게 '진짜 오는구나'가 보인다
  답글을 단 사람은 followup_log.json 에 적혀 두 번 달지 않는다.

사용법 (SNS_자동화 폴더에서):
  python threads_followup.py                 # 최근 7일 내 giveaway 글의 키워드 댓글 목록 + DM 문구 (아무것도 안 올림)
  python threads_followup.py --yes           # 목록의 사람들에게 공개 답글을 단다 (DM 을 먼저 보낸 뒤에!)
  python threads_followup.py --yes --skip 사용자명,사용자명   # DM 이 막힌 사람 → '팔로우해 주시면' 답글
  python threads_followup.py --post <글ID>   # 특정 글만
토큰: C:\\Users\\USER\\.sns_threads_token.txt (값은 출력하지 않는다)
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))

from threads_client import list_replies, publish_reply, recent_posts  # noqa: E402

TOKEN_FILE = Path.home() / ".sns_threads_token.txt"
USER_ID = "28088463677489445"
LOG = HERE / "followup_log.json"
KST = timezone(timedelta(hours=9))

REPLY_SENT = [
    "DM으로 보내드렸습니다. 확인해 보세요.",
    "방금 DM 넣어 뒀습니다. 채워 보시고 막히는 칸 있으면 거기로 물어 주세요.",
    "자료 DM으로 보냈습니다. 댓글 고맙습니다.",
    "보내드렸습니다. DM함 열어 보세요.",
]
REPLY_FOLLOW = [
    "DM 보내려 했는데 팔로우가 안 돼 있어 막혔습니다. 팔로우해 주시면 바로 보내드립니다.",
    "DM이 안 열려서 아직 못 보냈습니다. 팔로우 눌러 주시면 다시 보내드릴게요.",
]
DM_TEMPLATE = (
    "댓글 고맙습니다. 말씀하신 자료입니다.\n"
    "{link}\n"
    "채워 보시고 막히는 칸이 있으면 이 DM으로 업종과 인원만 보내 주세요. 봐 드립니다."
)


def load_log() -> dict:
    if LOG.exists():
        return json.loads(LOG.read_text(encoding="utf-8"))
    return {"replied": {}}


def save_log(log: dict) -> None:
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def giveaway_index(calendar: dict) -> dict:
    """첫 줄(앞 20자) → {keyword, asset_url, category}"""
    base = calendar.get("giveaway_assets_base", "").rstrip("/") + "/"
    idx = {}
    for cat, topic in calendar["posts"].items():
        for g in topic.get("giveaway", []):
            body = g.get("threads") or g.get("text") or ""
            key = body.strip().split("\n")[0][:20]
            idx[key] = {"keyword": g.get("keyword", "자료"), "asset": base + g.get("asset", ""), "category": cat}
    return idx


def main():
    args = sys.argv[1:]
    yes = "--yes" in args
    skip = set()
    if "--skip" in args:
        skip = set(args[args.index("--skip") + 1].split(","))
    only_post = args[args.index("--post") + 1] if "--post" in args else None

    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    calendar = json.loads((HERE / "content_calendar.json").read_text(encoding="utf-8"))
    gidx = giveaway_index(calendar)
    log = load_log()
    me = "junipapamasimaro"

    since = datetime.now(KST) - timedelta(days=7)
    targets = []
    for p in recent_posts(USER_ID, token, limit=20):
        if only_post and p["id"] != only_post:
            continue
        ts = datetime.fromisoformat(p["timestamp"].replace("+0000", "+00:00")).astimezone(KST)
        if ts < since and not only_post:
            continue
        key = (p.get("text") or "").strip()[:20]
        meta = gidx.get(key)
        if not meta and not only_post:
            continue
        targets.append((p, ts, meta))

    if not targets:
        print("최근 7일 안에 자료 배포(giveaway) 글이 없습니다.")
        return

    n_reply = 0
    for p, ts, meta in targets:
        keyword = meta["keyword"] if meta else ""
        print(f"\n=== {ts:%m-%d %H:%M} [{meta['category'] if meta else '?'}] 키워드 '{keyword}'  {p.get('permalink','')}")
        replies = list_replies(p["id"], token)
        others = [r for r in replies if r.get("username") and r["username"] != me]
        if not others:
            print("  댓글 없음")
            continue
        for r in others:
            text = (r.get("text") or "").strip()
            hit = (keyword and keyword in text) or (not keyword)
            done = r["id"] in log["replied"]
            flag = "✔답글완료" if done else ("키워드" if hit else "일반댓글(사람이 직접 답)")
            print(f"  @{r['username']:<22} {flag:<16} {text[:50]}")
            if not hit or done:
                continue
            if yes:
                pool = REPLY_FOLLOW if r["username"] in skip else REPLY_SENT
                msg = pool[n_reply % len(pool)]
                publish_reply(USER_ID, token, r["id"], msg)
                log["replied"][r["id"]] = {"user": r["username"], "post": p["id"], "at": datetime.now(KST).isoformat(), "msg": msg}
                save_log(log)
                n_reply += 1
        if meta and not yes:
            print("\n  --- DM 에 붙여 넣을 문구 (앱에서 사람이 보낸다) ---")
            print("  " + DM_TEMPLATE.format(link=meta["asset"]).replace("\n", "\n  "))

    if yes:
        print(f"\n공개 답글 {n_reply}개 완료. 기록: {LOG.name}")
    else:
        print("\n(아무것도 올리지 않았습니다. DM 을 보낸 뒤 --yes 로 다시 돌리면 공개 답글을 답니다. DM 이 막힌 사람은 --skip 사용자명)")


if __name__ == "__main__":
    main()
