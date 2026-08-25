import os
import time

import requests

GRAPH_API_VERSION = "v26.0"

IMAGE_PATH = "images/haedeok-credential-slide.png"
CAPTION = (
    "이 많은 자격증과 인증 경험, 다 이유가 있습니다.\n\n"
    "인증전공 박해덕 컨설턴트가 ISO 9001·14001·45001부터 ESG 지속가능보고서, "
    "벤처기업 인증까지 직접 실무로 대응합니다.\n\n"
    "우리 회사에 필요한 인증이 궁금하시면 댓글 남겨주세요. 확인 후 답변드립니다.\n\n"
    "#ISO인증 #품질경영시스템 #ESG컨설팅 #벤처기업인증 #인증전문가 #씨앤씨파트너"
)


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
    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["IG_ACCESS_TOKEN"]
    image_base_url = os.environ["IMAGE_BASE_URL"].rstrip("/")

    image_url = f"{image_base_url}/{IMAGE_PATH}"
    print(f"신뢰도 배지 게시 시작 — 이미지: {image_url}")

    creation_id = create_media_container(ig_user_id, access_token, image_url, CAPTION)
    time.sleep(5)
    result = publish_media(ig_user_id, access_token, creation_id)
    print("게시 완료:", result)


if __name__ == "__main__":
    main()
