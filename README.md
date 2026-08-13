# 황매산 숲속야영장 잔여자리(카라반/캠퍼하우스) 알림 봇

2026-08-16 ~ 08-17(1박), 카라반/캠퍼하우스 잔여자리가 새로 생기면 카카오톡 "나에게 보내기"로 알려줍니다.

## 구성

- `check_availability.py` : hc.go.kr 잔여자리 조회 → 이전 상태와 비교 → 알림 트리거
- `kakao_notify.py` : 카카오톡 나에게 보내기 전송
- `get_kakao_token.py` : 최초 1회, 리프레시 토큰 발급용 (로컬 PC에서 실행)
- `.github/workflows/check.yml` : 15분마다 자동 실행

## 설정 순서

### 1. 카카오 디벨로퍼스 앱 준비
`get_kakao_token.py` 상단 주석의 안내를 따라 앱을 만들고 REST API 키를 확인합니다.

### 2. 리프레시 토큰 발급 (내 PC에서 1회만)

```bash
pip install requests
python get_kakao_token.py
```

출력된 `refresh_token`을 보관해둡니다.

### 3. GitHub 저장소 생성 및 이 폴더 업로드

이 폴더 전체를 새 GitHub 저장소에 push 합니다.

### 4. GitHub Secrets 등록

저장소 **Settings > Secrets and variables > Actions**에서:

- `KAKAO_REST_API_KEY` : 카카오 디벨로퍼스 REST API 키
- `KAKAO_REFRESH_TOKEN` : 2번 단계에서 발급받은 리프레시 토큰

### 5. state.json 최초 생성

저장소에 빈 `state.json`을 하나 커밋해두세요 (없어도 첫 실행 시 자동 생성되지만,
git push 권한 문제를 피하려면 미리 만들어두는 걸 권장합니다).

```json
{"available": []}
```

### 6. 워크플로 확인

**Actions** 탭에서 `황매산 잔여자리 확인` 워크플로가 15분 간격으로 도는지 확인합니다.
`workflow_dispatch`로 수동 실행도 가능합니다.

## 날짜/시설 변경

`.github/workflows/check.yml`의 env 값을 바꾸면 됩니다.

- `TARGET_DATE` : 체크인 날짜 (YYYY-MM-DD)
- `CAMP_NIGHT` : 숙박 일수
- `SITE_GUBUNS` : `G01`=카라반, `G02`=캠퍼하우스, `G03`=텐트사이트 (쉼표로 여러 개 지정 가능)

## 참고 / 주의사항

- hc.go.kr은 `robots.txt`로 자동 접근을 명시적으로 막아두고 있습니다. 이 스크립트의 운영 여부는
  본인 판단하에 결정하시고, 요청 주기를 과도하게 짧게 잡지 않는 것을 권장합니다(기본 15분).
- 사이트 개편 시 `check_availability.py`의 파싱 로직이 깨질 수 있습니다.
- 카카오 액세스 토큰은 6시간 만료지만, 매 실행마다 리프레시 토큰으로 새로 발급받으므로
  별도 갱신 로직이 필요 없습니다. (단, 리프레시 토큰 자체도 카카오 정책상 만료·회전될 수 있어
  알림이 갑자기 안 오면 `get_kakao_token.py`를 다시 실행해 재발급하세요.)
