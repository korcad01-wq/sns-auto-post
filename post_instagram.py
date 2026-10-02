"""content_calendar.json(v2) 의 오늘 게시물을 골라 Instagram 에 올린다.

로테이션 (2026-10-03~, 하루 1회):
  d       = start_date 부터 경과일 (0부터)
  형식    = formats[d % 3]        card / question / case
  주제    = categories[d % 20]
  변형    = (d // 60) % 2         같은 주제·형식은 60일마다, 같은 글은 120일마다
  case    = cases[(d // 3) % len(cases)], 비어 있으면 그 주제의 '다른' question 으로 대체

환경변수:
  IG_USER_ID, IG_ACCESS_TOKEN, IMAGE_BASE_URL  (필수)
  POST_DATE=YYYY-MM-DD   테스트용 날짜 덮어쓰기
  DRY_RUN=1              선택 결과만 출력하고 게시하지 않음
"""
import json
import os
import time
from datetime import date

import requests

GRAPH_API_VERSION = "v26.0"


def pick_todays_post(calendar: dict, today: date):
    """오늘 게시물을 정규화한 dict 로 돌려준다.
    {"format", "category", "image"(없으면 None), "caption", "threads_text", "blog"}"""
    start = date.fromisoformat(calendar["start_date"])
    d = (today - start).days
    if d < 0:
        return None

    formats = calendar.get("formats", ["card", "question", "case"])
    categories = calendar["categories"]
    fmt = formats[d % len(formats)]
    category = categories[d % len(categories)]
    variant = d // (len(formats) * len(categories))
    topic = calendar["posts"][category]

    if fmt == "case":
        cases = calendar.get("cases") or []
        if cases:
            c = cases[(d // len(formats)) % len(cases)]
            return {
                "format": "case", "category": category,
                "image": c["image"], "caption": c["caption"],
                "threads_text": c.get("threads_text") or _strip_hashtags(c["caption"]),
                "blog": c.get("blog", ""),
            }
        fmt, variant = "question", variant + 1  # 사례가 없으면 다른 질문으로 대체

    if fmt == "card":
        items = topic["card"]
        item = items[variant % len(items)]
        return {
            "format": "card", "category": category,
            "image": item["image"], "caption": item["caption"],
            "threads_text": _strip_hashtags(item["caption"]),
            "blog": topic.get("blog", ""),
        }

    items = topic["question"]
    item = items[variant % len(items)]
    return {
        "format": "question", "category": category,
        "image": item.get("image"),  # Instagram 용 텍스트 카드. Threads 는 텍스트 전용으로 올린다
        "caption": item["text"] + "\n\n" + topic.get("hashtags", ""),
        "threads_text": item["text"],
        "blog": topic.get("blog", ""),
    }


def _strip_hashtags(caption: str) -> str:
    lines = [ln for ln in caption.split("\n")
             if not (ln.strip() and all(w.startswith("#") for w in ln.split()))]
    return "\n".join(lines).strip()


def load_calendar() -> dict:
    with open("content_calendar.json", encoding="utf-8") as f:
        return json.load(f)


def resolve_today() -> date:
    override = os.environ.get("POST_DATE", "").strip()
    return date.fromisoformat(override) if override else date.today()


def create_media_container(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media"
    resp = requests.post(url, data={
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    })
    if resp.status_code >= 400:
        print("Meta API 에러 응답:", resp.text)
    resp.raise_for_status()
    return resp.json()["id"]


def publish_media(ig_user_id: str, access_token: str, creation_id: str) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media_publish"
    resp = requests.post(url, data={
        "creation_id": creation_id,
        "access_token": access_token,
    })
    if resp.status_code >= 400:
        print("Meta API 에러 응답:", resp.text)
    resp.raise_for_status()
    return resp.json()


def main():
    calendar = load_calendar()
    today = resolve_today()
    post = pick_todays_post(calendar, today)
    if post is None:
        print(f"{today.isoformat()}: 시작일 이전이라 게시하지 않습니다.")
        return

    print(f"{today.isoformat()} 선택: {post['format']} / {post['category']} / 이미지 {post['image']}")
    if os.environ.get("DRY_RUN"):
        print("--- caption ---")
        print(post["caption"])
        return

    if not post["image"]:
        print("Instagram: 이미지가 없는 게시물이라 건너뜁니다(Threads 텍스트 전용).")
        return

    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["IG_ACCESS_TOKEN"]
    image_base_url = os.environ["IMAGE_BASE_URL"].rstrip("/")
    image_url = f"{image_base_url}/{post['image']}"

    print(f"게시 시작 — 이미지: {image_url}")
    creation_id = create_media_container(ig_user_id, access_token, image_url, post["caption"])
    time.sleep(5)  # Instagram 이 이미지를 가져와 처리할 시간
    result = publish_media(ig_user_id, access_token, creation_id)
    print("게시 완료:", result)


if __name__ == "__main__":
    main()
