# Handler for price commands
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
            
            if response.status_code == 200:
                price_data = response.json()
                
                # Format the change percentage with color emoji
                change = price_data.get('change_24h', 0)
                change_emoji = "📈" if change >= 0 else "📉"
                
                message = (
                    "📊 **XRP Price Information**\n\n"
                    f"💵 **Current Price:** ${price_data['price_usd']:.4f}\n"
                    f"{change_emoji} **24h Change:** {change:+.2f}%\n"
                    f"💹 **Market Cap:** ${price_data.get('market_cap', 0):,.0f}\n"
                    f"📊 **24h Volume:** ${price_data.get('volume_24h', 0):,.0f}\n\n"
                    f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                raise Exception("Price service unavailable")
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error**\n\n"
            f"Could not retrieve price: {str(e)}\n\n"
            "Try again in a few moments.",
            parse_mode=ParseMode.MARKDOWN
        )