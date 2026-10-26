"""
황매산 숲속야영장 '잔여자리 예약' 알림 (텔레그램).
체크인일 당일 또는 그 이후에는 자동으로 감시를 건너뛴다.
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

BASE_URL = "https://www.hc.go.kr/camp/apply/site/list.do"

TARGET_DATE = os.environ.get("TARGET_DATE", "2026-10-31")
CAMP_NIGHT = os.environ.get("CAMP_NIGHT", "1")
SITE_GUBUNS = os.environ.get("SITE_GUBUNS", "G01,G02,G03").split(",")
PERSON_CNT = os.environ.get("PERSON_CNT", "1")

STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
KST = ZoneInfo("Asia/Seoul")

FACILITY_PATTERN = re.compile(r"\[(카라반|캠퍼하우스|텐트사이트)\]\s*([^\s<][^<\n]{0,20})")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.hc.go.kr/09464/09499/09501.web",
}


def fetch_availability() -> set[str]:
    params = [("siteGubuns", g) for g in SITE_GUBUNS] + [
        ("appSdate", TARGET_DATE),
        ("campNight", CAMP_NIGHT),
        ("appGubun", "COMMON"),
        ("cpage", "1"),
        ("personCnt", PERSON_CNT),
    ]
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    if "예약가능한 시설이 없습니다" in resp.text:
        return set()
    return {f"[{g}] {n.strip()}" for g, n in FACILITY_PATTERN.findall(resp.text)}


def load_previous_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("available", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(available: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps({"available": sorted(available)}, ensure_ascii=False, indent=2),
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
    target = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()
    if today >= target:
        print(f"[건너뜀] 체크인일({target}) 당일 또는 그 이후라 감시 종료")
        return 0

    current = fetch_availability()
    previous = load_previous_state()
    newly_available = current - previous

    print(f"[조회 대상] {TARGET_DATE} ({CAMP_NIGHT}박) / {SITE_GUBUNS}")
    print(f"[현재 잔여] {sorted(current) if current else '없음'}")

    if newly_available:
        lines = "\n".join(f"- {name}" for name in sorted(newly_available))
        message = (
            f"[황매산 숲속야영장] {TARGET_DATE} 잔여자리 알림\n\n{lines}\n\n"
            "예약: https://www.hc.go.kr/09464/09499/09501.web"
        )
        failed = send_notifications(message)
        save_state(current)
        return 1 if failed else 0

    print("[변화 없음]")
    save_state(current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
