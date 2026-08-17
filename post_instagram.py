import json
import os
import time
from datetime import date, timedelta

import requests

GRAPH_API_VERSION = "v26.0"
POSTING_WEEKDAYS = (0, 2, 4)  # 월, 수, 금 (0=월요일)


def count_posting_days(start: date, end: date) -> int:
    count = 0
    d = start
    while d <= end:
        if d.weekday() in POSTING_WEEKDAYS:
            count += 1
        d += timedelta(days=1)
    return count


def pick_todays_post(calendar: dict, today: date):
    if today.weekday() not in POSTING_WEEKDAYS:
        return None

    start_date = date.fromisoformat(calendar["start_date"])
    if today < start_date:
        return None

    post_number = count_posting_days(start_date, today) - 1  # 0-indexed
    categories = calendar["categories"]
    category = categories[post_number % len(categories)]

    posts = calendar["posts"].get(category, [])
    if not posts:
        print(f"'{category}' 카테고리에 등록된 게시물이 없어 건너뜁니다.")
        return None

    within_category_index = (post_number // len(categories)) % len(posts)
    return posts[within_category_index]


def create_media_container(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media"
    resp = requests.post(url, data={
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
        
        if resp.status_code >= 400:
    print("Meta API 에러 응답:", resp.text)
                         
    })
    resp.raise_for_status()
    return resp.json()["id"]


def publish_media(ig_user_id: str, access_token: str, creation_id: str) -> dict:
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media_publish"
    resp = requests.post(url, data={
        "creation_id": creation_id,
        "access_token": access_token,
    })
    resp.raise_for_status()
    return resp.json()


def main():
    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["IG_ACCESS_TOKEN"]
    image_base_url = os.environ["IMAGE_BASE_URL"].rstrip("/")

    with open("content_calendar.json", encoding="utf-8") as f:
        calendar = json.load(f)

    today = date.today()
    post = pick_todays_post(calendar, today)
    if post is None:
        print(f"{today.isoformat()}: 오늘은 게시 예정이 없습니다.")
        return

    image_url = f"{image_base_url}/{post['image']}"
    caption = post["caption"]

    print(f"게시 시작 — 이미지: {image_url}")
    creation_id = create_media_container(ig_user_id, access_token, image_url, caption)

    time.sleep(5)  # Instagram이 이미지를 가져와 처리할 시간 확보

    result = publish_media(ig_user_id, access_token, creation_id)
    print("게시 완료:", result)


if __name__ == "__main__":
    main()
