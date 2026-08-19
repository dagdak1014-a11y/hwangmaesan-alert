"""
텔레그램 봇으로 메시지 전송.

필요 환경변수
- TELEGRAM_BOT_TOKEN : @BotFather 로 발급받은 봇 토큰
- TELEGRAM_CHAT_ID   : 알림을 받을 내 채팅방 ID
"""

from __future__ import annotations

import os

import requests


def send_telegram_message(message: str) -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": chat_id, "text": message},
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"텔레그램 전송 실패: {result}")
