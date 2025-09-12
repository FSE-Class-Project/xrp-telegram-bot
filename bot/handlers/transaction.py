# bot/handlers/transaction.py
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import httpx
import re
import uuid

from ..utils.formatting import (
    format_transaction_confirmation,
    format_transaction_success,
    format_error_message,
    format_hash,
    format_xrp_address,
    escape_html,
)
from ..keyboards.menus import keyboards

# --- Conversation States ---
# Define states for the multi-step "send" process
AMOUNT, ADDRESS, CONFIRM = range(3)

# --- Conversation Handlers ---

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the send conversation flow (via /send or inline button)."""
    # If triggered from an inline button, answer the callback
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    msg = update.effective_message
    if not msg or not update.effective_user or context.user_data is None:
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
                await msg.reply_text("❌ <b>Invalid Amount</b>\n\nPlease enter a positive number.", parse_mode=ParseMode.HTML)
                return ConversationHandler.END

            if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
                await msg.reply_text("❌ <b>Invalid Address</b>\n\nThe XRP address format is incorrect.", parse_mode=ParseMode.HTML)
                return ConversationHandler.END

            # Store data in the user-specific context
            context.user_data['transaction'] = {'amount': amount, 'address': address}
            
            # Ask for confirmation
            keyboard = [[KeyboardButton("✅ YES"), KeyboardButton("❌ NO")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            fee = 0.00001  # Standard fee
            message = format_transaction_confirmation(address, amount, fee)
            await msg.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return CONFIRM
        except (ValueError, IndexError):
            await msg.reply_text("Invalid command format. Use <code>/send [amount] [address]</code> or just <code>/send</code>.", parse_mode=ParseMode.HTML)
            return ConversationHandler.END
    else:
        # --- Interactive mode ---
        cancel_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
        )
        await msg.reply_text(
            "💵 <b>Send XRP</b>\n\nHow much XRP would you like to send?",
            reply_markup=cancel_markup,
            parse_mode=ParseMode.HTML
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
        cancel_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
        )
        await update.message.reply_text(
            "📬 <b>Recipient Address</b>\n\nEnter the destination XRP address.",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_markup,
        )
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
    
    fee = 0.00001  # Standard fee
    message = format_transaction_confirmation(address, amount, fee)
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
            api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
            
            # Generate idempotency key for this transaction
            idempotency_key = f"tg_{update.effective_user.id}_{uuid.uuid4().hex[:16]}"
            
            headers = {
                "X-API-Key": api_key,
                "Idempotency-Key": idempotency_key
            }
            response = await client.post(
                f"{api_url}/api/v1/transaction/send",
                json={
                    "from_telegram_id": str(update.effective_user.id),
                    "to_address": tx_data['address'],
                    "amount": tx_data['amount']
                },
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            await processing_msg.delete()

            if data.get("success"):
                tx_hash = data.get('tx_hash', 'N/A')
                explorer_url = f"https://testnet.xrpl.org/transactions/{tx_hash}"
                message = format_transaction_success(tx_hash, explorer_url)
                await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            else:
                error = data.get('error', 'Unknown error')
                await update.message.reply_text(
                    format_error_message(f"Transaction Failed\n\nReason: {error}"),
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(
            format_error_message(f"Transaction Failed\n\nAn error occurred: {str(e)}"),
            parse_mode=ParseMode.HTML
        )
    finally:
        context.user_data.pop('transaction', None)
    
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the transaction conversation (works with /cancel or inline button)."""
    # Support cancel via callback button
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        cq_msg = update.callback_query.message
    else:
        msg = update.message

    if context.user_data is not None:
        context.user_data.pop('transaction', None)
        # Update nav state to main menu for consistency
        try:
            context.user_data["current_menu"] = "main_menu"
        except Exception:
            pass

    # Show main menu after cancellation
    try:
        if update.callback_query and cq_msg:
            await cq_msg.edit_text(
                "❌ <b>Transaction Cancelled</b>\n\n🏠 <b>Main Menu</b>\n\nWhat would you like to do?",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )
        elif msg:
            await msg.reply_text(
                "❌ <b>Transaction Cancelled</b>\n\n🏠 <b>Main Menu</b>\n\nWhat would you like to do?",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )
    except Exception:
        # Silent fallback
        pass
    return ConversationHandler.END

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command to show transaction history."""
    if not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
            
            headers = {"X-API-Key": api_key}
            response = await client.get(f"{api_url}/api/v1/transaction/history/{user_id}?limit=10", headers=headers)
            response.raise_for_status()
            
            data = response.json()
            transactions = data.get('transactions', [])
            
            if not transactions:
                await update.message.reply_text("📜 <b>Transaction History</b>\n\nNo transactions found.", parse_mode=ParseMode.HTML)
                return
            
            message = "📜 <b>Recent Transactions</b>\n\n"
            for i, tx in enumerate(transactions[:10], 1):
                status_icon = "✅" if tx['status'] == 'success' else "❌"
                message += f"{i}. {status_icon} {tx['amount']:.6f} XRP\n"
                
                # Format recipient address safely
                recipient = tx['recipient']
                if len(recipient) > 16:
                    formatted_recipient = f"{recipient[:10]}...{recipient[-6:]}"
                else:
                    formatted_recipient = recipient
                message += f"   <b>To:</b> {format_xrp_address(formatted_recipient)}\n"
                
                # Format hash if available
                if tx.get('hash'):
                    message += f"   <b>Hash:</b> {format_hash(tx['hash'], length=10)}\n"
                    
                message += f"   <b>Date:</b> {tx['timestamp'][:10]}\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = "❌ <b>Not Registered</b>\n\nYou need to register first!\nUse /start to create your wallet."
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = format_error_message(f"Could not retrieve history: {str(e)}")
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)
