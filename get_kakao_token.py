"""
최초 1회만 로컬(내 PC)에서 실행해서 리프레시 토큰을 발급받는 스크립트.

사전 준비 (카카오 디벨로퍼스, developers.kakao.com)
1. 애플리케이션 추가
2. [앱 설정 > 플랫폼]에서 Web 플랫폼 등록 (사이트 도메인은 아무 값이나, 예: http://localhost)
3. [제품설정 > 카카오 로그인] 활성화
4. [제품설정 > 카카오 로그인 > Redirect URI]에 아래 REDIRECT_URI와 동일한 값 등록
   (실제로 그 주소가 열릴 필요는 없음. 브라우저 주소창에서 code만 복사할 것이므로)
5. [제품설정 > 카카오 로그인 > 동의항목]에서 "카카오톡 메시지 전송"(talk_message) 항목을
   사용 설정 (필요시 검수 없이 개인 개발자 계정으로는 바로 사용 가능한 경우가 많음)
6. [앱 설정 > 앱 키]에서 REST API 키 확인

사용법
1. 아래 REST_API_KEY, REDIRECT_URI를 채운다.
2. 스크립트를 실행하면 인가 URL이 출력된다. 브라우저로 열어 카카오 로그인/동의한다.
3. 리다이렉트된 주소창의 URL에서 `code=` 뒤의 값을 복사해 이 스크립트에 붙여넣는다.
4. 액세스 토큰/리프레시 토큰이 출력된다.
5. 리프레시 토큰을 GitHub 저장소의 Secrets(KAKAO_REFRESH_TOKEN)에 등록한다.
"""

import requests

REST_API_KEY = "16bfbb56622854d9260095e541b3808d"
REDIRECT_URI = "http://localhost"  # 카카오 디벨로퍼스에 등록한 값과 동일해야 함

AUTHORIZE_URL = (
    "https://kauth.kakao.com/oauth/authorize"
    f"?client_id={REST_API_KEY}"
    f"&redirect_uri={REDIRECT_URI}"
    "&response_type=code"
    "&scope=talk_message"
)

TOKEN_URL = "https://kauth.kakao.com/oauth/token"


def main() -> None:
    print("1) 아래 URL을 브라우저에서 열고 로그인/동의하세요:\n")
    print(AUTHORIZE_URL)
    print(
        "\n2) 리다이렉트된 주소(예: http://localhost/?code=XXXXXXXX)에서 "
        "code= 뒤의 값을 복사하세요."
    )
    code = input("\n인가 코드(code)를 붙여넣으세요: ").strip()

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        timeout=10,
    )
    resp.raise_for_status()
    tokens = resp.json()

    print("\n=== 발급 결과 ===")
    print(f"access_token  : {tokens['access_token']}")
    print(f"refresh_token : {tokens['refresh_token']}")
    print(
        "\n이제 refresh_token 값을 GitHub 저장소 Settings > Secrets and variables "
        "> Actions 에 KAKAO_REFRESH_TOKEN 이름으로 등록하세요.\n"
        "REST_API_KEY는 KAKAO_REST_API_KEY 이름으로 등록하세요."
    )


if __name__ == "__main__":
    main()
