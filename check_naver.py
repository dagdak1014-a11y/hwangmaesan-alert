"""
네이버 스마트스토어(브랜드스토어) 상품 페이지(들)가 '구매 가능' 상태로 바뀌면 알림.

여러 상품을 동시에 감시할 수 있다 (NAVER_PRODUCT_URLS 를 쉼표로 구분해서 여러 개 지정).

동작 방식
1. 각 상품 페이지 HTML을 그대로 요청한다.
2. 아래 SOLDOUT_MARKERS 문구가 있으면 품절, 없으면 구매 가능으로 판단한다.
   (네이버 스마트스토어는 CSS 클래스명이 빌드마다 바뀌는 해시값이라 클래스 대신
   고정된 한글 문구로 판단한다.)
3. 직전 상태(naver_state.json)와 비교해서 품절 -> 구매가능 으로 바뀐 상품이 있으면
   알림을 보낸다.

주의
- 이 페이지가 자바스크립트로 나중에 내용을 채우는 방식이라면(서버가 최초 응답에
  상품 상태를 포함하지 않는다면), 이 방식으로는 정확히 판단하지 못할 수 있다.
  최초 실행 로그의 [현재 상태]가 실제 화면과 일치하는지 꼭 확인할 것.
- 사이트가 개편되면 판단 기준(문구)이 바뀔 수 있다.
- 요청 간격을 너무 짧게 잡지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

PRODUCT_URLS = [
    u.strip()
    for u in os.environ.get(
        "NAVER_PRODUCT_URLS",
        "https://brand.naver.com/thankstamp/products/5080326648",
    ).split(",")
    if u.strip()
]

STATE_FILE = Path(os.environ.get("NAVER_STATE_FILE", "naver_state.json"))

SOLDOUT_MARKERS = (
    "구매하실 수 없는 상품",
    "상품 품절",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def fetch_is_available(url: str) -> bool:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text
    is_soldout = any(marker in html for marker in SOLDOUT_MARKERS)
    return not is_soldout


def load_previous_state() -> dict[str, bool]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, bool]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_notifications(message: str) -> bool:
    had_failure = False

    try:
        from kakao_notify import send_kakao_memo

        send_kakao_memo(message)
        print("[알림] 카카오톡 전송 완료")
    except Exception as exc:  # noqa: BLE001
        print(f"[카카오 알림 실패] {exc}", file=sys.stderr)
        had_failure = True

    try:
        from telegram_notify import send_telegram_message

        send_telegram_message(message)
        print("[알림] 텔레그램 전송 완료")
    except Exception as exc:  # noqa: BLE001
        print(f"[텔레그램 알림 실패] {exc}", file=sys.stderr)
        had_failure = True

    return had_failure


def main() -> int:
    previous_state = load_previous_state()
    new_state: dict[str, bool] = {}
    had_any_failure = False

    for url in PRODUCT_URLS:
        current = fetch_is_available(url)
        previous = bool(previous_state.get(url, False))
        new_state[url] = current

        print(f"[조회 대상] {url}")
        print(f"[현재 상태] {'구매 가능' if current else '품절'}")

        became_available = current and not previous
        if became_available:
            print("[상태 변화] 품절 -> 구매 가능")
            message = f"[네이버/땡스탬프] 상품이 구매 가능해졌습니다!\n\n{url}"
            if send_notifications(message):
                had_any_failure = True
        else:
            print("[변화 없음]")

    save_state(new_state)
    return 1 if had_any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
