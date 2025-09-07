# bot/handlers/price.py
from telegram import Update, ParseMode
from telegram.ext import ContextTypes
import httpx
from datetime import datetime

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command"""
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{context.bot_data['api_url']}/api/v1/price/current",
                timeout=10.0
            )
            
            data = response.json()
            
            if data.get("success"):
                # Format change percentage with emoji
                change = data.get('change_24h', 0)
                change_emoji = "📈" if change >= 0 else "📉"
                
                message = (
                    "📊 *XRP Price Information*\n\n"
                    f"💵 *Current Price:* ${data.get('price_usd', 0):.4f}\n"
                    f"{change_emoji} *24h Change:* {change:+.2f}%\n"
                    f"💹 *Market Cap:* ${data.get('market_cap', 0):,.0f}\n"
                    f"📊 *24h Volume:* ${data.get('volume_24h', 0):,.0f}\n\n"
                    f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}_"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ *Error*\n\n" + data.get("error", "Price service unavailable"),
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error*\n\nCould not retrieve price: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )