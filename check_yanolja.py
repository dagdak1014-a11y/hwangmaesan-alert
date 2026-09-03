"""
야놀자(nol.yanolja.com) 숙소 상세 페이지에서, 존(zone)별로(예: 오토사이트존,
데크사이트존) 예약 가능한 객실이 생기면 알림.

동작 방식
1. 상품 페이지 HTML을 그대로 요청한다 (서버 렌더링 데이터 안에 각 객실 타입의
   zoneName 과 invalidReasonType(품절 사유)이 구조화된 형태로 포함되어 있음을
   확인했다. invalidReasonType 이 "SOLD_OUT" 이면 품절, null 이면 예약 가능).
2. zoneName 별로 묶어서, 그 존에 하나라도 invalidReasonType 이 null(예약 가능)인
   객실 타입이 있으면 그 존은 '예약 가능'으로 판단한다.
3. 직전 상태(yanolja_state.json)와 비교해서 품절 -> 가능 으로 바뀐 (URL, 존)
   조합이 있으면 알린다.

환경변수
- YANOLJA_URL   : 감시할 숙소 상세 페이지 URL (체크인/체크아웃 날짜 포함)
- YANOLJA_ZONES : 감시할 존 이름, 쉼표로 구분 (기본값: "오토사이트존,데크사이트존")

주의
- 야놀자가 자동화 요청(특히 데이터센터 IP)을 차단할 가능성이 있다. 이 경우
  타임아웃/차단 오류가 나면 r.jina.ai 같은 프록시를 거치는 방식으로 바꿔야 한다.
- 사이트가 개편되면 판단 기준(JSON 필드명)이 바뀔 수 있다.
- 요청 간격을 너무 짧게 잡지 않는다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

URL = os.environ.get(
    "YANOLJA_URL",
    "https://nol.yanolja.com/stay/domestic/10070074"
    "?verticalCategory=PRODUCT_CATEGORY_KOREA_ACCOMMODATION"
    "&checkInDate=2026-09-19&checkOutDate=2026-09-20&adultCount=2",
)
ZONES = [
    z.strip()
    for z in os.environ.get("YANOLJA_ZONES", "오토사이트존,데크사이트존").split(",")
    if z.strip()
]

STATE_FILE = Path(os.environ.get("YANOLJA_STATE_FILE", "yanolja_state.json"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# 서버 렌더링 데이터(이스케이프된 JSON 문자열) 안에서
# zoneName 과 그 뒤에 나오는 invalidReasonType 값을 짝지어 추출한다.
ZONE_STATUS_PATTERN = re.compile(
    r'zoneName\\+"\s*:\s*\\+"([^\\"]+)\\+".*?'
    r'invalidReasonType\\+"\s*:\s*(null|\\+"[^\\"]*\\+")',
)


def fetch_zone_availability() -> dict[str, bool]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    zone_has_available: dict[str, bool] = {zone: False for zone in ZONES}
    for zone, reason in ZONE_STATUS_PATTERN.findall(html):
        if zone not in zone_has_available:
            continue
        if reason == "null":
            zone_has_available[zone] = True
    return zone_has_available


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
    current_by_zone = fetch_zone_availability()
    previous_state = load_previous_state()

    new_state = dict(previous_state)
    had_any_failure = False

    for zone, current in current_by_zone.items():
        key = f"{URL}::{zone}"
        previous = bool(previous_state.get(key, False))
        new_state[key] = current

        print(f"[조회 대상] {zone}")
        print(f"[현재 상태] {'예약 가능' if current else '품절'}")

        became_available = current and not previous
        if became_available:
            print(f"[상태 변화] {zone}: 품절 -> 예약 가능")
            message = f"[야놀자] {zone}에 예약 가능한 객실이 생겼습니다!\n\n{URL}"
            if send_notifications(message):
                had_any_failure = True
        else:
            print("[변화 없음]")

    save_state(new_state)
    return 1 if had_any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
