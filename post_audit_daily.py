import os
import time

import requests

GRAPH_API_VERSION = "v26.0"

IMAGE_PATH = "images/audit-consult-sns.png"
CAPTION = (
    "ISO 심사 전, 내부심사·경영검토서 작성 고민이시죠?\n"
    "씨앤씨파트너가 고민을 해결해드립니다.\n\n"
    "1. 부서별 절차서 이행 여부 확인\n"
    "2. 경영방침·목표 달성 결과 확인\n"
    "3. 부서별 현장 내부심사 종합평가\n"
    "4. 시스템 운영 문제점 확인\n"
    "5. 향후 시스템 운영방안 수립\n"
    "6. 부서별 세부 실천계획 수립\n"
    "7. 경영자 검토서 작성\n\n"
    "품질·환경·안전보건 매뉴얼 및 절차서 작성도 함께 지원합니다.\n\n"
    "궁금하시면 댓글에 '내부심사' 남겨주세요. 확인 후 답변드립니다.\n\n"
    "#내부심사 #경영검토보고서 #ISO심사대응 #절차서작성 #품질경영시스템 #중소기업지원"
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
    print(f"내부심사·경영검토 게시 시작 — 이미지: {image_url}")

    creation_id = create_media_container(ig_user_id, access_token, image_url, CAPTION)
    time.sleep(5)
    result = publish_media(ig_user_id, access_token, creation_id)
    print("게시 완료:", result)


if __name__ == "__main__":
    main()
