"""
영도 마리노 오토캠핑장(yeongdo.go.kr) '잔여사이트 선착순 예약' 특정 날짜/시설의
잔여자리가 생기면, 어떤 자리가 비었는지(사이트 번호)까지 포함해서 알림.

동작 방식
1. 사이트 내부 API(/marinocamping/camp/apply/site/list.do)를 직접 호출한다.
   (hc.go.kr 황매산 캠핑장과 동일한 예약 시스템(SCMS)을 사용하고 있어 같은 방식으로 접근 가능함.)
2. 응답 HTML에서 예약 가능한 사이트(class="siteCode ..." + title="예약가능")의
   이름(예: '오토 2')을 모두 추출한다.
3. 직전 상태(marino_state.json)와 비교해서 새로 생긴 사이트가 있으면 그 목록과 함께 알린다.

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
import re
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

# 예약 가능한 사이트 블록 안에서 버튼 텍스트(사이트 이름, 예: '오토 2')를 추출.
# 가능한 사이트는 class="siteCode ..." 로 시작하고, 그 안의 <button ...>이름</button>에
# disabled 속성이 없다 (품절 사이트는 class="unselect ..." + disabled).
AVAILABLE_BLOCK_PATTERN = re.compile(
    r'class="siteCode[^"]*".*?<button[^>]*title="예약가능"[^>]*>\s*([^<\r\n]+?)\s*(?:<|$)',
    re.DOTALL,
)


def fetch_available_sites() -> list[str]:
    params = {
        "siteGubun": SITE_GUBUN,
        "appSdate": APP_SDATE,
        "campNight": CAMP_NIGHT,
        "appGubun": "COMMON",
        "personCnt": PERSON_CNT,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text
    return [m.strip() for m in AVAILABLE_BLOCK_PATTERN.findall(html)]


def load_previous_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("available_sites", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(available_sites: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {"available_sites": sorted(available_sites)},
            ensure_ascii=False,
            indent=2,
        ),
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
    current_sites = set(fetch_available_sites())
    previous_sites = load_previous_state()

    print(f"[조회 대상] {APP_SDATE} ({CAMP_NIGHT}박) / siteGubun={SITE_GUBUN}")
    print(f"[현재 잔여] {sorted(current_sites) if current_sites else '없음'}")

    newly_available = current_sites - previous_sites

    if newly_available:
        print(f"[새로 생긴 잔여자리] {sorted(newly_available)}")
        lines = "\n".join(f"- {name}" for name in sorted(newly_available))
        message = (
            f"[영도 마리노 오토캠핑장] {APP_SDATE} 잔여자리 알림\n\n"
            f"{lines}\n\n"
            "https://www.yeongdo.go.kr/marinocamping/00003/00015/00028.web"
        )

        had_failure = send_notifications(message)
        save_state(current_sites)
        return 1 if had_failure else 0

    print("[변화 없음]")
    save_state(current_sites)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
