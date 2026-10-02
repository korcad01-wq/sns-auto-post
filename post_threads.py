"""content_calendar.json(v2) 의 오늘 게시물을 Threads 에 올린다.

선택 로직은 post_instagram.pick_todays_post 를 그대로 써서 두 채널이 같은 날 같은 주제를 낸다.
- card / case : 이미지 + 본문
- question    : 텍스트 전용 (이미지 없음 → 블로그 링크가 미리보기 카드로 붙는다)
본문 끝에 주제별 블로그 링크가 있으면 '자세한 글' 줄을 붙인다. 해시태그 줄은 넣지 않는다.
"""
import os

from post_instagram import load_calendar, pick_todays_post, resolve_today
from threads_client import fit_text, publish_image, publish_text, threads_env


def build_text(post: dict) -> str:
    text = post["threads_text"].strip()
    blog = (post.get("blog") or "").strip()
    if blog:
        text = f"{text}\n\n자세한 글 → {blog}"
    return fit_text(text)


def main():
    calendar = load_calendar()
    today = resolve_today()
    post = pick_todays_post(calendar, today)
    if post is None:
        print(f"{today.isoformat()}: 시작일 이전이라 게시하지 않습니다.")
        return

    text = build_text(post)
    print(f"{today.isoformat()} Threads 선택: {post['format']} / {post['category']} ({len(text)}자)")
    if os.environ.get("DRY_RUN"):
        print("--- threads text ---")
        print(text)
        return

    env = threads_env()
    if env is None:
        return
    user_id, token = env

    if post["format"] == "question":
        publish_text(user_id, token, text)
        return

    image_base_url = os.environ["IMAGE_BASE_URL"].rstrip("/")
    publish_image(user_id, token, f"{image_base_url}/{post['image']}", text)


if __name__ == "__main__":
    main()
