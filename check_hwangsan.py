"""
황산캠핑장(hscamping.yssisul.or.kr) 특정 날짜의 예약 가능 여부 알림 (텔레그램).

- 예약 페이지 HTML 안의 숨김 입력값(id="actDate")에
  "20261030:16,20261031:0,..." 형태로 날짜별 잔여 자리 수가 들어 있다.
- 감시 날짜의 잔여 자리가 0 -> 1 이상으로 바뀌는 순간에만 알림을 보낸다.
- 상태 파일에는 날짜별 '예약 가능 여부(true/false)'만 저장한다.
- 이 사이트는 당일 예약도 가능하므로, 감시는 해당 날짜가 지난 뒤 자동으로 멈춘다.
- actDate 값을 찾지 못하면 상태를 건드리지 않고 오류로 종료한다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

URL = os.environ.get(
    "HS_URL",
    "https://hscamping.yssisul.or.kr:453/rsvc/rsv_srm.html?b_id=hscamping",
)
TARGET_DATES = [
    d.strip()
    for d in os.environ.get("HS_TARGET_DATES", "2026-10-31").split(",")
    if d.strip()
]

STATE_FILE = Path(os.environ.get("HS_STATE_FILE", "hwangsan_state.json"))
KST = ZoneInfo("Asia/Seoul")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

ACT_DATE_TAG = re.compile(r"<input[^>]*id=[\"']actDate[\"'][^>]*>", re.IGNORECASE)
VALUE_ATTR = re.compile(r"value=[\"']([^\"']*)[\"']", re.IGNORECASE)


def parse_remaining(html: str) -> dict[str, int]:
    tag = ACT_DATE_TAG.search(html)
    value = VALUE_ATTR.search(tag.group(0)) if tag else None
    if not value:
        raise RuntimeError("actDate 값을 찾지 못했습니다 (사이트 구조 변경 가능성)")

    remaining: dict[str, int] = {}
    for item in value.group(1).split(","):
        if ":" not in item:
            continue
        ymd, count = item.split(":", 1)
        if len(ymd) != 8 or not ymd.isdigit() or not count.strip().isdigit():
            continue
        remaining[f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"] = int(count)
    if not remaining:
        raise RuntimeError("actDate 값이 비어 있습니다 (사이트 구조 변경 가능성)")
    return remaining


def fetch_remaining() -> dict[str, int]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"[진단] status={resp.status_code} final_url={resp.url} length={len(resp.text)}")
    resp.raise_for_status()
    try:
        return parse_remaining(resp.text)
    except RuntimeError:
        text = resp.text
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        print(f"[진단] title={title.group(1).strip() if title else None}")
        print(f"[진단] 'actDate' 문자열 포함 여부: {'actDate' in text}")
        print(f"[진단] 응답 앞부분:\n{text[:800]}")
        raise


def load_previous_state() -> dict[str, bool]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, bool]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def send_notifications(message: str) -> bool:
    """텔레그램 전송. 실패하면 True 반환."""
    try:
        from telegram_notify import send_telegram_message

        send_telegram_message(message)
        print("[알림] 텔레그램 전송 완료")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"[텔레그램 알림 실패] {exc}", file=sys.stderr)
        return True


def main() -> int:
    today = datetime.now(KST).date()
    active = [
        d for d in TARGET_DATES
        if datetime.strptime(d, "%Y-%m-%d").date() >= today
    ]
    for d in TARGET_DATES:
        if d not in active:
            print(f"[건너뜀] {d} — 이미 지난 날짜라 감시 종료")
    if not active:
        return 0

    remaining = fetch_remaining()
    previous_state = load_previous_state()
    new_state = dict(previous_state)
    failed = False

    for date in active:
        count = remaining.get(date, 0)
        available = count > 0
        was_available = bool(previous_state.get(date, False))
        new_state[date] = available

        print(f"[조회 대상] {date}")
        print(f"[현재 상태] {'예약 가능 (잔여 ' + str(count) + ')' if available else '매진'}")

        if available and not was_available:
            print("[상태 변화] 매진 -> 예약 가능")
            message = (
                f"[황산캠핑장] {date} 예약 가능한 자리가 생겼습니다! (잔여 {count})\n\n"
                f"{URL}"
            )
            if send_notifications(message):
                failed = True
        else:
            print("[변화 없음]")

    save_state(new_state)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
