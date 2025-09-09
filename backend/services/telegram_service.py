"""Telegram API service"""
import httpx
from backend.config import settings

class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    async def send_message(
        self, 
        chat_id: int, 
        text: str,
        parse_mode: str = "MarkdownV2",
        reply_markup: dict | None = None
    ) -> dict:
        """Send message via Telegram API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "reply_markup": reply_markup
                }
            )
            return response.json()
    
    async def set_webhook(self, url: str) -> bool:
        """Register webhook with Telegram"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/setWebhook",
                json={
                    "url": url,
                    "secret_token": settings.TELEGRAM_WEBHOOK_SECRET
                }
            )
            result = response.json()
            return result.get("ok", False)

telegram_service = TelegramService()