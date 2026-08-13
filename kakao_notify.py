"""
카카오톡 '나에게 보내기' 메시지 전송.

필요 환경변수
- KAKAO_REST_API_KEY : 카카오 디벨로퍼스 앱의 REST API 키
- KAKAO_REFRESH_TOKEN : get_kakao_token.py로 최초 1회 발급받은 리프레시 토큰

동작
- 리프레시 토큰으로 매번 새 액세스 토큰을 발급받아 사용한다
  (액세스 토큰은 6시간 만료, 리프레시 토큰으로 자동 갱신되므로 별도 저장 불필요).
"""

from __future__ import annotations

import json
import os

import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _refresh_access_token() -> str:
    rest_api_key = os.environ["KAKAO_REST_API_KEY"]
    refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def send_kakao_memo(message: str) -> None:
    access_token = _refresh_access_token()

    template_object = {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": "https://www.hc.go.kr/09464/09499/09501.web",
            "mobile_web_url": "https://www.hc.go.kr/09464/09499/09501.web",
        },
    }

    resp = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("result_code") != 0:
        raise RuntimeError(f"카카오 전송 실패: {result}")
