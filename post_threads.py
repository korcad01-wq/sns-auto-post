"""content_calendar.json 의 오늘 게시물(Instagram과 동일)을 Threads에 올린다.

게시물 선택 로직은 post_instagram.py 의 pick_todays_post 를 그대로 재사용해서
Instagram 과 Threads 가 항상 같은 이미지·캡션을 내보낸다.
"""
import json
import os
from datetime import date

from post_instagram import pick_todays_post
from threads_client import publish_image, threads_env, threads_text


def main():
    env = threads_env()
    if env is None:
        return
    user_id, token = env
    image_base_url = os.environ["IMAGE_BASE_URL"].rstrip("/")

    with open("content_calendar.json", encoding="utf-8") as f:
        calendar = json.load(f)

    slot = os.environ.get("SLOT", "AM")
    today = date.today()
    post = pick_todays_post(calendar, today, slot)
    if post is None:
        print(f"{today.isoformat()} ({slot}): 오늘 이 시간대는 게시 예정이 없습니다.")
        return

    image_url = f"{image_base_url}/{post['image']}"
    text = post.get("threads_caption") or threads_text(post["caption"])
    publish_image(user_id, token, image_url, text)


if __name__ == "__main__":
    main()
