"""Telegram webhook handler"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import hmac

from backend.database.connection import get_db
from backend.services.user_service import user_service
from backend.services.telegram_service import telegram_service
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
    _: bool = Depends(verify_telegram_signature),
    db: Session = Depends(get_db)
) -> dict:
    """Main webhook handler"""
    
    # Extract message or callback query
    message = update.get("message")
    
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
    if user.wallet:
        await telegram_service.send_message(
            chat_id=chat_id,
            text=f"Welcome! Your XRP address: `{user.wallet.xrp_address}`",
            parse_mode="MarkdownV2"
        )
    else:
        await telegram_service.send_message(
            chat_id=chat_id,
            text="Welcome! Setting up your wallet\\.\\.\\.",
            parse_mode="MarkdownV2"
        )
    
    return {"ok": True}

async def handle_balance_command(db: Session, user_id: int, chat_id: int) -> dict:
    """Handle /balance command"""
    # Get user
    user = user_service.get_user_by_telegram_id(db, str(user_id))
    if not user:
        await telegram_service.send_message(
            chat_id=chat_id,
            text="Please use /start to register first\\.",
            parse_mode="MarkdownV2"
        )
        return {"ok": True}
    
    # Update and get balance
    balance = await user_service.update_balance(db, user)
    
    # Send balance message
    await telegram_service.send_message(
        chat_id=chat_id,
        text=f"💰 *Balance:* {balance:.6f} XRP",
        parse_mode="MarkdownV2"
    )
    
    return {"ok": True}

async def handle_send_command(db: Session, user_id: int, chat_id: int, text: str) -> dict:
    """Handle /send command"""
    # Parse command: /send <address> <amount>
    parts = text.split()
    if len(parts) != 3:
        await telegram_service.send_message(
            chat_id=chat_id,
            text="Usage: /send \\<address\\> \\<amount\\>",
            parse_mode="MarkdownV2"
        )
        return {"ok": True}
    
    _, recipient_address, amount_str = parts
    
    try:
        amount = float(amount_str)
    except ValueError:
        await telegram_service.send_message(
            chat_id=chat_id,
            text="Invalid amount\\. Please enter a number\\.",
            parse_mode="MarkdownV2"
        )
        return {"ok": True}
    
    # Get user
    user = user_service.get_user_by_telegram_id(db, str(user_id))
    if not user:
        await telegram_service.send_message(
            chat_id=chat_id,
            text="Please use /start to register first\\.",
            parse_mode="MarkdownV2"
        )
        return {"ok": True}
    
    # Send XRP
    result = await user_service.send_xrp(
        db=db,
        sender=user,
        recipient_address=recipient_address,
        amount=amount
    )
    
    if result["success"]:
        await telegram_service.send_message(
            chat_id=chat_id,
            text=f"✅ Sent {amount} XRP to `{recipient_address}`\\nTx: `{result.get('tx_hash', 'N/A')}`",
            parse_mode="MarkdownV2"
        )
    else:
        error_msg = result.get("error", "Transaction failed").replace(".", "\\.")
        await telegram_service.send_message(
            chat_id=chat_id,
            text=f"❌ Failed: {error_msg}",
            parse_mode="MarkdownV2"
        )
    
    return {"ok": True}

async def handle_price_command(chat_id: int) -> dict:
    """Handle /price command"""
    # Get current XRP price using httpx directly
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "ripple",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true"
                }
            )
            
            if response.status_code == 200:
                data = response.json()["ripple"]
                price = data.get("usd", 0)
                change_24h = data.get("usd_24h_change", 0)
                change_emoji = "📈" if change_24h > 0 else "📉"
                
                await telegram_service.send_message(
                    chat_id=chat_id,
                    text=f"💱 *XRP Price*\n\n"
                         f"USD: \\${price:.4f}\n"
                         f"24h Change: {change_emoji} {change_24h:.2f}%",
                    parse_mode="MarkdownV2"
                )
            else:
                raise Exception("Failed to fetch price")
    except Exception:
        await telegram_service.send_message(
            chat_id=chat_id,
            text="Unable to fetch price data\\. Please try again later\\.",
            parse_mode="MarkdownV2"
        )
    
    return {"ok": True}

async def handle_help_command(chat_id: int) -> dict:
    """Handle /help command"""
    help_text = (
        "*XRP Telegram Bot Commands*\n\n"
        "/start \\- Register and get your XRP wallet\n"
        "/balance \\- Check your XRP balance\n"
        "/send \\<address\\> \\<amount\\> \\- Send XRP\n"
        "/price \\- Get current XRP price\n"
        "/help \\- Show this help message\n\n"
        "_Your wallet is automatically created and funded on testnet_"
    )
    
    await telegram_service.send_message(
        chat_id=chat_id,
        text=help_text,
        parse_mode="MarkdownV2"
    )
    
    return {"ok": True}