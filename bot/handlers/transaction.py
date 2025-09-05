from telegram import Update, ParseMode
from telegram.ext import ContextTypes
import httpx
import re

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /send command - Send XRP"""
    user_id = update.effective_user.id
    
    # Parse command arguments
    args = context.args
    
    if len(args) != 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "**Usage:** `/send [amount] [address]`\n"
            "**Example:** `/send 10 rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        amount = float(args[0])
        address = args[1]
        
        # Validate amount
        if amount <= 0:
            await update.message.reply_text(
                "❌ **Invalid Amount**\n\n"
                "Please enter a valid positive number.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Validate address format (basic check)
        if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
            await update.message.reply_text(
                "❌ **Invalid Address**\n\n"
                "The XRP address you entered is invalid.\n"
                "XRP addresses start with 'r' and are 25-34 characters.\n\n"
                "Example: `rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ Processing transaction...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        async with httpx.AsyncClient() as client:
            # Send transaction via API
            response = await client.post(
                f"{context.bot_data['api_url']}/api/v1/transaction/send",
                json={
                    "from_telegram_id": str(user_id),
                    "to_address": address,
                    "amount": amount
                },
                timeout=60.0  # Longer timeout for blockchain transactions
            )
            
            # Delete processing message
            await processing_msg.delete()
            
            if response.status_code == 200:
                result = response.json()
                
                message = (
                    "✅ **Transaction Successful!**\n\n"
                    f"**Amount:** {amount:.6f} XRP\n"
                    f"**To:** `{address}`\n"
                    f"**Fee:** {result.get('fee', 0.00001):.6f} XRP\n\n"
                    f"**Transaction Hash:**\n"
                    f"`{result['tx_hash']}`\n\n"
                    f"View on explorer:\n"
                    f"https://testnet.xrpl.org/transactions/{result['tx_hash']}"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
            elif response.status_code == 404:
                await update.message.reply_text(
                    "❌ **Not Registered**\n\n"
                    "You need to register first!\n"
                    "Use /start to create your wallet.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                error = response.json().get('detail', 'Unknown error')
                
                await update.message.reply_text(
                    f"❌ **Transaction Failed**\n\n"
                    f"**Reason:** {error}\n\n"
                    "Please check your balance and try again.\n"
                    "Use /balance to check your current balance.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except ValueError:
        await update.message.reply_text(
            "❌ **Invalid Amount**\n\n"
            "Please enter a valid number for the amount.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        # Try to delete processing message if it exists
        try:
            await processing_msg.delete()
        except:
            pass
            
        await update.message.reply_text(
            f"❌ **Transaction Failed**\n\n"
            f"**Error:** {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )