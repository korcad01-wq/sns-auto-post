"""Instagram 계정·게시물 지표를 읽어 로그로 출력한다(읽기 전용, 게시 없음).

Actions → IG Insights → Run workflow 로 실행. 로그의 'IGROW ' / 'IGDAY ' / 'IGACC ' 줄을 로컬에서 모아 분석한다.
  IGACC {json}  계정: 팔로워 수·게시물 수
  IGROW {json}  게시물 1건: 시각·형식·캡션 앞 40자·좋아요·댓글·도달·저장·공유·조회·프로필방문·팔로우
  IGDAY {json}  일별 계정 지표(reach, follower_count 등) — API 가 주는 범위만

환경변수: IG_USER_ID, IG_ACCESS_TOKEN, SINCE(YYYY-MM-DD, 기본 2026-06-01)
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests

V = "v26.0"
G = f"https://graph.facebook.com/{V}"
MEDIA_METRICS = ["reach", "likes", "comments", "saved", "shares", "views", "total_interactions",
                 "profile_visits", "follows"]


def get(url, **params):
    r = requests.get(url, params=params, timeout=60)
    return r.status_code, r.json()


def media_insights(mid, token):
    out = {}
    code, j = get(f"{G}/{mid}/insights", metric=",".join(MEDIA_METRICS), access_token=token)
    if code < 400:
        for m in j.get("data", []):
            out[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
        return out
    for metric in MEDIA_METRICS:  # 한 지표라도 안 되면 묶음 전체가 실패 → 하나씩
        code, j = get(f"{G}/{mid}/insights", metric=metric, access_token=token)
        if code < 400 and j.get("data"):
            m = j["data"][0]
            out[metric] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
    return out


def main():
    uid, token = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    since = datetime.fromisoformat(os.environ.get("SINCE") or "2026-06-01").replace(tzinfo=timezone.utc)

    code, acc = get(f"{G}/{uid}", fields="username,followers_count,follows_count,media_count", access_token=token)
    print("IGACC " + json.dumps(acc, ensure_ascii=False))

    url, params = f"{G}/{uid}/media", {"fields": "id,caption,timestamp,media_type,media_product_type,like_count,comments_count",
                                       "limit": 50, "access_token": token}
    n = 0
    while url:
        code, j = get(url, **params) if params else get(url)
        if code >= 400:
            print("media 조회 실패:", json.dumps(j)[:300])
            break
        stop = False
        for m in j.get("data", []):
            ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
            if ts < since:
                stop = True
                break
            row = {"id": m["id"], "ts": ts.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
                   "type": m.get("media_product_type") or m.get("media_type"), "media_type": m.get("media_type"),
                   "cap": (m.get("caption") or "").replace("\n", " ")[:40],
                   "like": m.get("like_count"), "cmt": m.get("comments_count")}
            row.update(media_insights(m["id"], token))
            print("IGROW " + json.dumps(row, ensure_ascii=False))
            n += 1
            time.sleep(0.3)
        if stop:
            break
        url, params = j.get("paging", {}).get("next"), None
    print(f"게시물 {n}건")

    # 일별 계정 지표: 30일 창으로 나눠 조회(API 제한). 안 되는 지표는 건너뜀
    end = datetime.now(timezone.utc)
    start = max(since, end - timedelta(days=120))
    for metric in ("reach", "follower_count"):
        s = start
        while s < end:
            e = min(s + timedelta(days=29), end)
            code, j = get(f"{G}/{uid}/insights", metric=metric, period="day",
                          since=int(s.timestamp()), until=int(e.timestamp()), access_token=token)
            if code >= 400:
                print(f"{metric} {s.date()}~{e.date()} 실패:", json.dumps(j.get("error", {}).get("message", ""))[:200])
            else:
                for d in j.get("data", []):
                    for v in d.get("values", []):
                        print("IGDAY " + json.dumps({"metric": metric, "date": v["end_time"][:10], "value": v["value"]}))
            s = e


if __name__ == "__main__":
    main()
