# bot/handlers/transaction.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from html import escape
import httpx
import re

# --- Conversation States ---
# Define states for the multi-step "send" process
AMOUNT, ADDRESS, CONFIRM = range(3)

# --- Conversation Handlers ---

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the /send conversation flow."""
    if not update.message or not update.effective_user or context.user_data is None:
        return ConversationHandler.END

    # Use context.user_data for state management
    context.user_data['transaction'] = {}
    
    # context.args is guaranteed to exist, so we can check its length
    if context.args and len(context.args) == 2:
        # --- Direct command: /send [amount] [address] ---
        try:
            amount = float(context.args[0])
            address = context.args[1]

            if amount <= 0:
                await update.message.reply_text("❌ <b>Invalid Amount</b>\n\nPlease enter a positive number.", parse_mode=ParseMode.HTML)
                return ConversationHandler.END

            if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
                await update.message.reply_text("❌ <b>Invalid Address</b>\n\nThe XRP address format is incorrect.", parse_mode=ParseMode.HTML)
                return ConversationHandler.END

            # Store data in the user-specific context
            context.user_data['transaction'] = {'amount': amount, 'address': address}
            
            # Ask for confirmation
            keyboard = [[KeyboardButton("✅ YES"), KeyboardButton("❌ NO")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            total = amount + 0.00001 # Assuming a static fee for display
            message = (
                f"📤 <b>Confirm Transaction</b>\n\n"
                f"<b>To:</b> <code>{escape(address)}</code>\n"
                f"<b>Amount:</b> {amount:.6f} XRP\n"
                f"<b>Total (incl. fee):</b> {total:.6f} XRP\n\n"
                f"⚠️ <i>Please review carefully.</i>\n\n"
                f"Reply <b>YES</b> to confirm or <b>NO</b> to cancel."
            )
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return CONFIRM
        except (ValueError, IndexError):
            await update.message.reply_text("Invalid command format. Use <code>/send [amount] [address]</code> or just <code>/send</code>.", parse_mode=ParseMode.HTML)
            return ConversationHandler.END
    else:
        # --- Interactive mode ---
        await update.message.reply_text(
            "💵 <b>Send XRP</b>\n\nHow much XRP would you like to send?",
            reply_markup=ReplyKeyboardRemove()
        )
        return AMOUNT

async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the amount input and asks for the address."""
    if not update.message or not update.message.text or context.user_data is None:
        return ConversationHandler.END

    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("Please enter a positive number for the amount.", parse_mode=ParseMode.HTML)
            return AMOUNT

        context.user_data.setdefault('transaction', {})['amount'] = amount
        await update.message.reply_text("📬 <b>Recipient Address</b>\n\nEnter the destination XRP address.", parse_mode=ParseMode.HTML)
        return ADDRESS
    except ValueError:
        await update.message.reply_text("That's not a valid number. Please try again.", parse_mode=ParseMode.HTML)
        return AMOUNT

async def address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the address input and asks for confirmation."""
    if not update.message or not update.message.text or context.user_data is None:
        return ConversationHandler.END

    address = update.message.text.strip()
    if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
        await update.message.reply_text("Invalid address format. It must start with 'r'. Please try again.", parse_mode=ParseMode.HTML)
        return ADDRESS
    
    context.user_data.setdefault('transaction', {})['address'] = address
    amount = context.user_data.get('transaction', {}).get('amount', 0)

    keyboard = [[KeyboardButton("✅ YES"), KeyboardButton("❌ NO")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    total = amount + 0.00001
    message = (
        f"📤 <b>Confirm Transaction</b>\n\n"
        f"<b>To:</b> <code>{escape(address)}</code>\n"
        f"<b>Amount:</b> {amount:.6f} XRP\n"
        f"<b>Total (incl. fee):</b> {total:.6f} XRP\n\n"
        f"Reply <b>YES</b> to confirm."
    )
    await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    return CONFIRM

async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the final confirmation and executes the transaction."""
    if not update.message or not update.message.text or not update.effective_user or context.user_data is None:
        return ConversationHandler.END
    
    if "YES" not in update.message.text.upper():
        await update.message.reply_text("❌ Transaction cancelled.", reply_markup=ReplyKeyboardRemove())
        context.user_data.pop('transaction', None)
        return ConversationHandler.END

    tx_data = context.user_data.get('transaction')
    if not tx_data:
        await update.message.reply_text("Error: Transaction data not found. Please start over with /send.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    processing_msg = await update.message.reply_text("⏳ Processing transaction...", reply_markup=ReplyKeyboardRemove())
    
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            response = await client.post(
                f"{api_url}/api/v1/transaction/send",
                json={
                    "from_telegram_id": str(update.effective_user.id),
                    "to_address": tx_data['address'],
                    "amount": tx_data['amount']
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            await processing_msg.delete()

            if data.get("success"):
                tx_hash = escape(data.get('tx_hash', 'N/A'))
                explorer_url = f"https://testnet.xrpl.org/transactions/{tx_hash}"
                message = (
                    f"✅ <b>Transaction Successful!</b>\n\n"
                    f"<b>Hash:</b> <code>{tx_hash}</code>\n\n"
                    f'<a href="{explorer_url}">View on Explorer</a>'
                )
                await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            else:
                error = escape(data.get('error', 'Unknown error'))
                await update.message.reply_text(f"❌ <b>Transaction Failed</b>\n\n<b>Reason:</b> {error}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(f"❌ <b>Transaction Failed</b>\n\nAn error occurred: <code>{escape(str(e))}</code>", parse_mode=ParseMode.HTML)
    finally:
        context.user_data.pop('transaction', None)
    
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the transaction conversation."""
    if not update.message or context.user_data is None:
        return ConversationHandler.END
    context.user_data.pop('transaction', None)
    await update.message.reply_text("❌ Transaction cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Placeholder for the /history command."""
    if not update.message:
        return
    await update.message.reply_text("<i>Fetching transaction history... (feature coming soon)</i>", parse_mode=ParseMode.HTML)

