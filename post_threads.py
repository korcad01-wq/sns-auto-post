"""content_calendar.json(v3) 의 오늘 게시물을 Threads 에 올린다.

선택 로직은 post_instagram.pick_todays_post 를 그대로 써서 두 채널이 같은 날 같은 주제를 낸다.
v3 (2026-10-10, 쓰레드 자동화 전자책 반영):
- 본문은 항목의 'threads' (3~5줄, 첫 줄에 내가, 번호·소제목·링크·해시태그 없음)
- 본문에 링크를 넣지 않는다 (전자책 실측: 링크 글 1,388회 vs 무링크 28,333회). 블로그 링크는 DM·프로필로
- question·card 는 텍스트 전용, giveaway 는 표지 이미지 1장 + 본문
- giveaway 는 게시 뒤 내 첫 답글(팔로우 안내) 1개를 자동으로 단다. 다른 답글은 사람이 단다
- 오늘 같은 첫 줄의 글이 이미 있으면 건너뛴다 (로컬 21:00 트리거 + GitHub cron 백업 중복 방지)
"""
import os
import re
import time

from post_instagram import load_calendar, pick_todays_post, resolve_today
from threads_client import (already_posted_today, fit_text, publish_image, publish_reply,
                            publish_text, threads_env)


def build_text(post: dict, calendar: dict) -> str:
    text = post["threads_text"].strip()
    blog = (post.get("blog") or "").strip()
    if blog and calendar.get("threads_link_in_body", False):
        text = f"{text}\n\n자세한 글 → {blog}"
    return fit_text(text)


def final_check(text: str, calendar: dict) -> list:
    """전자책 6부 '발행 직전 검사': 0자·링크·해시태그·번호 목록·9줄 초과."""
    problems = []
    if not text.strip():
        problems.append("본문이 비어 있음")
    if not calendar.get("threads_link_in_body", False) and re.search(r"https?://|www\.", text):
        problems.append("본문에 링크")
    if re.search(r"(^|\s)#\S", text):
        problems.append("본문에 해시태그")
    if re.search(r"^\s*\d+\.\s", text, re.M):
        problems.append("번호 목록")
    if len([l for l in text.split("\n") if l.strip()]) > 9:
        problems.append("9줄 초과")
    return problems


def main():
    calendar = load_calendar()
    today = resolve_today()
    post = pick_todays_post(calendar, today)
    if post is None:
        print(f"{today.isoformat()}: 시작일 이전이거나 쉬는 요일이라 게시하지 않습니다.")
        return

    text = build_text(post, calendar)
    problems = final_check(text, calendar)
    print(f"{today.isoformat()} Threads 선택: {post['format']} / {post['category']} ({len(text)}자)")
    if os.environ.get("DRY_RUN"):
        print("--- threads text ---")
        print(text)
        if post.get("reply"):
            print("--- first reply ---")
            print(post["reply"])
        print("검사:", "통과" if not problems else problems)
        return
    if problems:
        print("Threads: 발행 직전 검사에 걸려 게시하지 않습니다:", problems)
        return

    env = threads_env()
    if env is None:
        return
    user_id, token = env

    if already_posted_today(user_id, token, text.split("\n")[0], today):
        print("Threads: 오늘 같은 글이 이미 올라가 있어 건너뜁니다(중복 방지).")
        return

    if post["format"] == "giveaway" and post.get("image"):
        image_base_url = os.environ["IMAGE_BASE_URL"].rstrip("/")
        result = publish_image(user_id, token, f"{image_base_url}/{post['image']}", text)
    else:
        result = publish_text(user_id, token, text)

    reply = (post.get("reply") or "").strip()
    if reply and result.get("id"):
        time.sleep(20)
        publish_reply(user_id, token, result["id"], reply)


if __name__ == "__main__":
    main()
