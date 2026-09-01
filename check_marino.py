"""
영도 마리노 오토캠핑장(yeongdo.go.kr) '잔여사이트 선착순 예약' 특정 날짜/시설의
잔여자리가 생기면 알림.

동작 방식
1. 사이트 내부 API(/marinocamping/camp/apply/site/list.do)를 직접 호출한다.
   (hc.go.kr 황매산 캠핑장과 동일한 예약 시스템(SCMS)을 사용하고 있어 같은 방식으로 접근 가능함.)
2. 응답 HTML에 '예약가능' 문구가 있으면 최소 한 자리 이상 잔여자리가 있는 것으로 판단한다.
3. 직전 상태(marino_state.json)와 비교해서 없음 -> 있음 으로 바뀌면 알림을 보낸다.

파라미터
- MARINO_SITE_GUBUN: G01=카라반, G02=오토사이트, G03=일반사이트
- MARINO_APP_SDATE: 체크인 날짜 (YYYY-MM-DD)
- MARINO_CAMP_NIGHT: 숙박 일수

주의
- 사이트가 개편되면 판단 기준(문구/클래스명)이 바뀔 수 있다.
- 요청 간격을 너무 짧게 잡지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

BASE_URL = "https://www.yeongdo.go.kr/marinocamping/camp/apply/site/list.do"

SITE_GUBUN = os.environ.get("MARINO_SITE_GUBUN", "G02")  # 오토사이트
APP_SDATE = os.environ.get("MARINO_APP_SDATE", "2026-09-19")
CAMP_NIGHT = os.environ.get("MARINO_CAMP_NIGHT", "1")
PERSON_CNT = os.environ.get("MARINO_PERSON_CNT", "1")

STATE_FILE = Path(os.environ.get("MARINO_STATE_FILE", "marino_state.json"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def fetch_is_available() -> bool:
    params = {
        "siteGubun": SITE_GUBUN,
        "appSdate": APP_SDATE,
        "campNight": CAMP_NIGHT,
        "appGubun": "COMMON",
        "personCnt": PERSON_CNT,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return "예약가능" in resp.text


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

    print(f"[조회 대상] {APP_SDATE} ({CAMP_NIGHT}박) / siteGubun={SITE_GUBUN}")
    print(f"[현재 상태] {'잔여자리 있음' if current else '잔여자리 없음'}")

    became_available = current and not previous

    if became_available:
        print("[상태 변화] 없음 -> 있음")
        message = (
            f"[영도 마리노 오토캠핑장] {APP_SDATE} 잔여자리가 생겼습니다!\n\n"
            "https://www.yeongdo.go.kr/marinocamping/00003/00015/00028.web"
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
