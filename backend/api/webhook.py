"""Telegram webhook handler"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import hmac
import hashlib
import json

from backend.database.connection import get_db
from backend.services import user_service, telegram_service
from backend.config import settings

webhook_router = APIRouter(prefix="/telegram", tags=["Telegram"])

def verify_telegram_signature(
    x_telegram_bot_api_secret_token: str = Header(None)
) -> bool:
    """Verify webhook came from Telegram"""
    if not x_telegram_bot_api_secret_token:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if not hmac.compare_digest(x_telegram_bot_api_secret_token, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
    return True

@webhook_router.post("/webhook")
async def handle_webhook(
    update: dict[str, Any],
    verified: bool = Depends(verify_telegram_signature),
    db: Session = Depends(get_db)
) -> dict:
    """Main webhook handler"""
    
    # Extract message or callback query
    message = update.get("message")
    callback_query = update.get("callback_query")
    
    if message:
        # Handle commands
        text = message.get("text", "")
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        
        if text.startswith("/start"):
            return await handle_start_command(db, user_id, chat_id)
        elif text.startswith("/balance"):
            return await handle_balance_command(db, user_id, chat_id)
        elif text.startswith("/send"):
            return await handle_send_command(db, user_id, chat_id, text)
        elif text.startswith("/price"):
            return await handle_price_command(chat_id)
        elif text.startswith("/help"):
            return await handle_help_command(chat_id)
    
    return {"ok": True}

async def handle_start_command(db: Session, user_id: int, chat_id: int) -> dict:
    """Handle /start command"""
    # Register user if new
    user = await user_service.create_or_get_user(
        db=db,
        telegram_id=str(user_id),
        telegram_username=None  # Get from update if available
    )
    
    # Send welcome message
    await telegram_service.send_message(
        chat_id=chat_id,
        text=f"Welcome! Your XRP address: `{user.wallet.xrp_address}`",
        parse_mode="MarkdownV2"
    )
    
    return {"ok": True}