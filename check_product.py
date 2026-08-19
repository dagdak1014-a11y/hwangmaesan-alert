"""
thankstamp.com 특정 상품 페이지가 '구매 가능' 상태로 바뀌면 알림.

동작 방식
1. 상품 페이지 HTML을 그대로 요청한다 (이 사이트는 서버 렌더링이라 JS 실행 없이도
   품절 여부가 HTML에 그대로 포함되어 있음을 확인했다).
2. 'btn_add_soldout' / 'btn_shop_soldout' 클래스 문자열이 있으면 품절, 없으면 구매 가능으로 판단한다.
3. 직전 상태(product_state.json)와 비교해서 품절 -> 구매가능 으로 바뀌었을 때만 알림을 보낸다.

주의
- 사이트가 개편되면 판단 기준(클래스명)이 바뀔 수 있다.
- 요청 간격을 너무 짧게 잡지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

PRODUCT_URL = os.environ.get(
    "PRODUCT_URL",
    "https://www.thankstamp.com/goods/goods_view.php?goodsNo=1000000024",
)
STATE_FILE = Path(os.environ.get("STATE_FILE", "product_state.json"))

SOLDOUT_MARKERS = ("btn_add_soldout", "btn_shop_soldout")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def fetch_is_available() -> bool:
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text
    is_soldout = any(marker in html for marker in SOLDOUT_MARKERS)
    return not is_soldout


def load_previous_state() -> bool:
    if not STATE_FILE.exists():
        return False
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return bool(data.get("available", False))
    except (json.JSONDecodeError, OSError):
        return False


def save_state(available: bool) -> None:
    STATE_FILE.write_text(
        json.dumps({"available": available}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    current = fetch_is_available()
    previous = load_previous_state()

    print(f"[조회 대상] {PRODUCT_URL}")
    print(f"[현재 상태] {'구매 가능' if current else '품절'}")

    became_available = current and not previous

    if became_available:
        print("[상태 변화] 품절 -> 구매 가능")
        message = (
            "[땡스탬프] 상품이 구매 가능해졌습니다!\n\n"
            f"{PRODUCT_URL}"
        )

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

        save_state(current)
        return 1 if had_failure else 0

    print("[변화 없음]")
    save_state(current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
