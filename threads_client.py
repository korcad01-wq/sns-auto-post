"""Threads API 게시 공용 모듈.

Instagram용 post_instagram.py 와 같은 이미지·캡션을 Threads에 올린다.
환경변수 THREADS_USER_ID / THREADS_ACCESS_TOKEN 이 없으면 건너뛰도록 설계했다
(토큰을 아직 안 넣은 상태에서도 Instagram 게시 워크플로가 깨지지 않게).
"""
import os
import time

import requests

THREADS_API = "https://graph.threads.net/v1.0"
TEXT_LIMIT = 500          # Threads 본문 글자 제한
CONTAINER_TIMEOUT = 180   # 컨테이너 처리 대기 최대 초


def threads_env():
    """(user_id, token) 를 돌려준다. 둘 중 하나라도 비어 있으면 None."""
    user_id = os.environ.get("THREADS_USER_ID", "").strip()
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        print("Threads: THREADS_USER_ID / THREADS_ACCESS_TOKEN 이 없어 건너뜁니다.")
        return None
    return user_id, token


def threads_text(caption: str) -> str:
    """Instagram 캡션을 Threads 용으로 다듬는다: 해시태그만 있는 줄은 뺀다.
    (Threads 는 해시태그가 링크로 안 걸리고 남용은 스팸 신호로 본다.)"""
    lines = [ln for ln in caption.split("\n")
             if not (ln.strip() and all(w.startswith("#") for w in ln.split()))]
    return "\n".join(lines).strip()


def fit_text(text: str) -> str:
    """500자 초과면 뒤쪽 줄부터 잘라내 맞춘다(해시태그 줄이 먼저 빠진다)."""
    if len(text) <= TEXT_LIMIT:
        return text
    lines = text.rstrip().split("\n")
    while lines and len("\n".join(lines)) > TEXT_LIMIT:
        lines.pop()
    fitted = "\n".join(lines).rstrip()
    if not fitted:  # 한 줄이 500자를 넘는 극단적 경우
        fitted = text[: TEXT_LIMIT - 1] + "…"
    print(f"Threads: 본문이 {len(text)}자라 {len(fitted)}자로 줄였습니다.")
    return fitted


def _check(resp: requests.Response) -> dict:
    if resp.status_code >= 400:
        print("Threads API 에러 응답:", resp.text)
    resp.raise_for_status()
    return resp.json()


def create_image_container(user_id: str, token: str, image_url: str, text: str) -> str:
    data = _check(requests.post(f"{THREADS_API}/{user_id}/threads", data={
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": fit_text(text),
        "access_token": token,
    }))
    return data["id"]


def wait_until_finished(container_id: str, token: str) -> None:
    """이미지 처리는 비동기라 status 가 FINISHED 될 때까지 기다린다."""
    deadline = time.time() + CONTAINER_TIMEOUT
    while True:
        data = _check(requests.get(f"{THREADS_API}/{container_id}", params={
            "fields": "status,error_message",
            "access_token": token,
        }))
        status = data.get("status")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads 컨테이너 실패: {data}")
        if time.time() > deadline:
            raise TimeoutError(f"Threads 컨테이너 처리 대기 초과: {data}")
        print(f"Threads: 컨테이너 상태 {status} … 5초 후 재확인")
        time.sleep(5)


def publish_container(user_id: str, token: str, creation_id: str) -> dict:
    return _check(requests.post(f"{THREADS_API}/{user_id}/threads_publish", data={
        "creation_id": creation_id,
        "access_token": token,
    }))


def publish_image(user_id: str, token: str, image_url: str, text: str) -> dict:
    """이미지 1장 + 본문을 Threads에 게시하고 결과(JSON)를 돌려준다."""
    print(f"Threads 게시 시작 — 이미지: {image_url}")
    creation_id = create_image_container(user_id, token, image_url, text)
    time.sleep(10)  # 공식 권장 대기(평균 30초)의 일부. 이후 status 폴링으로 보완
    wait_until_finished(creation_id, token)
    result = publish_container(user_id, token, creation_id)
    print("Threads 게시 완료:", result)
    return result
