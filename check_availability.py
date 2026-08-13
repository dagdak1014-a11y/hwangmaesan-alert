"""
황매산 숲속야영장 '잔여자리 예약' 카라반/캠퍼하우스 알림 봇

동작 방식
1. hc.go.kr의 잔여자리 조회 화면이 내부적으로 호출하는 site/list.do 엔드포인트를
   동일한 파라미터로 직접 호출한다.
2. 응답 HTML에서 "[카라반] xxx" / "[캠퍼하우스] xxx" 형태의 시설명을 추출한다.
3. 직전 실행 결과(state.json)와 비교해서 "새로 생긴" 시설명이 있으면
   카카오톡 나에게 보내기로 알림을 보낸다.
4. state.json을 갱신한다. (GitHub Actions에서는 워크플로가 커밋까지 담당)

주의
- hc.go.kr은 robots.txt로 자동 접근을 명시적으로 막고 있다(Disallow).
  이 스크립트를 실제로 배포/운영할지는 사용자 본인이 판단해서 결정할 것.
  요청 간격을 너무 짧게 잡지 말고(예: 10~15분 이상), 서버에 부담을 주지 않도록 한다.
- hc.go.kr 페이지 구조가 바뀌면 파싱 정규식이 깨질 수 있다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

BASE_URL = "https://www.hc.go.kr/camp/apply/site/list.do"

# 조회 대상: 환경변수로 오버라이드 가능 (기본값 = 8/16~17, 1박, 카라반+캠퍼하우스)
TARGET_DATE = os.environ.get("TARGET_DATE", "2026-08-16")  # 체크인일 (YYYY-MM-DD)
CAMP_NIGHT = os.environ.get("CAMP_NIGHT", "1")              # 숙박 일수
# G01=카라반, G02=캠퍼하우스, G03=텐트사이트 (사이트에서 체크박스 클릭 시 확인된 값)
SITE_GUBUNS = os.environ.get("SITE_GUBUNS", "G01,G02").split(",")
PERSON_CNT = os.environ.get("PERSON_CNT", "1")

STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))

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

    matches = FACILITY_PATTERN.findall(resp.text)
    return {f"[{gubun}] {name.strip()}" for gubun, name in matches}


def load_previous_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("available", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(available: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps({"available": sorted(available)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    current = fetch_availability()
    previous = load_previous_state()
    newly_available = current - previous

    print(f"[조회 대상] {TARGET_DATE} ({CAMP_NIGHT}박) / {SITE_GUBUNS}")
    print(f"[현재 잔여] {sorted(current) if current else '없음'}")

    if newly_available:
        print(f"[새로 생긴 잔여자리] {sorted(newly_available)}")
        from kakao_notify import send_kakao_memo  # 지연 임포트 (토큰 없어도 조회만은 동작하게)

        lines = "\n".join(f"- {name}" for name in sorted(newly_available))
        message = (
            f"[황매산 숲속야영장] {TARGET_DATE} 잔여자리 알림\n\n"
            f"{lines}\n\n"
            f"예약: https://www.hc.go.kr/09464/09499/09501.web"
        )
        try:
            send_kakao_memo(message)
            print("[알림] 카카오톡 전송 완료")
        except Exception as exc:  # noqa: BLE001
            print(f"[알림 실패] {exc}", file=sys.stderr)
            save_state(current)
            return 1
    else:
        print("[변화 없음] 새로운 잔여자리가 없습니다.")

    save_state(current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
