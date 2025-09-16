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
    format_warning_message,
    format_hash,
    format_xrp_address,
    escape_html,
)
from ..keyboards.menus import keyboards

# --- Conversation States ---
# Define states for the multi-step "send" process
MODE, BENEFICIARY_SELECT, BENEFICIARY_ADD_ALIAS, BENEFICIARY_ADD_ADDRESS, AMOUNT, ADDRESS, CONFIRM = range(7)


async def _send_prompt(message, text: str, reply_markup=None, edit: bool = False) -> None:
    """Edit the originating message when possible, otherwise send a new one."""
    if message is None:
        return

    if edit:
        try:
            await message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return
        except Exception:
            pass

    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

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
    context.user_data.pop('beneficiaries', None)
    context.user_data.pop('beneficiary_add', None)
    
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
        options_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📇 Beneficiary", callback_data="send_mode_beneficiary")],
                [InlineKeyboardButton("🔗 Enter Address", callback_data="send_mode_address")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")],
            ]
        )
        await msg.reply_text(
            "💵 <b>Send XRP</b>\n\nChoose how you'd like to send:",
            reply_markup=options_markup,
            parse_mode=ParseMode.HTML,
        )
        return MODE


async def send_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's choice between manual entry and beneficiaries."""
    if context.user_data is None or not update.callback_query or not update.effective_user:
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    choice = query.data or ""
    transaction_state = context.user_data.setdefault('transaction', {})

    if choice == "send_mode_address":
        # Reset any beneficiary-specific data and prompt for amount
        transaction_state.pop('address', None)
        transaction_state.pop('beneficiary_alias', None)

        cancel_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
        )
        await _send_prompt(
            query.message,
            "💵 <b>Send XRP</b>\n\nHow much XRP would you like to send?",
            reply_markup=cancel_markup,
            edit=True,
        )
        return AMOUNT

    if choice == "send_mode_beneficiary":
        return await _show_beneficiary_list(query, context)

    return ConversationHandler.END


async def _show_beneficiary_list(callback_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetch and display the user's saved beneficiaries."""
    if context.user_data is None or not callback_query or not callback_query.from_user:
        return ConversationHandler.END

    user_id = str(callback_query.from_user.id)
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/beneficiaries/{user_id}",
                headers=headers,
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        await _send_prompt(
            callback_query.message,
            format_error_message(f"Could not load beneficiaries.\n\n{detail}"),
            edit=True,
        )
        return ConversationHandler.END
    except Exception as exc:
        await _send_prompt(
            callback_query.message,
            format_error_message(f"Could not load beneficiaries.\n\n{str(exc)}"),
            edit=True,
        )
        return ConversationHandler.END

    beneficiaries = payload.get('beneficiaries', []) if isinstance(payload, dict) else []
    beneficiary_map: dict[str, dict[str, str]] = {}
    keyboard_rows: list[list[InlineKeyboardButton]] = []

    for entry in beneficiaries:
        b_id = str(entry.get('id'))
        alias = str(entry.get('alias', ''))
        address = str(entry.get('address', ''))
        if not b_id or not alias or not address:
            continue

        beneficiary_map[b_id] = {"alias": alias, "address": address}
        keyboard_rows.append(
            [InlineKeyboardButton(f"📇 {alias}", callback_data=f"beneficiary_select:{b_id}")]
        )

    keyboard_rows.append([InlineKeyboardButton("➕ Add Beneficiary", callback_data="beneficiary_add")])
    keyboard_rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")])

    context.user_data['beneficiaries'] = beneficiary_map

    if beneficiary_map:
        message_text = (
            "📇 <b>Saved Beneficiaries</b>\n\n"
            "Choose a beneficiary to use for this transaction or add a new one."
        )
    else:
        message_text = (
            "📇 <b>No Beneficiaries Yet</b>\n\n"
            "You can add a beneficiary to save an address for quick sends."
        )

    await _send_prompt(
        callback_query.message,
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        edit=True,
    )
    return BENEFICIARY_SELECT


async def beneficiary_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle beneficiary selection or start the add flow."""
    if context.user_data is None or not update.callback_query:
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    data = query.data or ""
    transaction_state = context.user_data.setdefault('transaction', {})

    if data == "beneficiary_add":
        context.user_data['beneficiary_add'] = {}
        prompt_text = (
            "➕ <b>Add Beneficiary</b>\n\n"
            "Send me a nickname for this beneficiary (e.g. <code>Mom</code>, <code>Cold Wallet</code>)."
        )
        cancel_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
        )
        await _send_prompt(query.message, prompt_text, reply_markup=cancel_markup, edit=True)
        return BENEFICIARY_ADD_ALIAS

    if data.startswith("beneficiary_select:"):
        beneficiary_id = data.split(":", 1)[1]
        beneficiary_map = context.user_data.get('beneficiaries', {}) or {}
        beneficiary = beneficiary_map.get(beneficiary_id)

        if not beneficiary:
            await query.message.reply_text(
                format_error_message("That beneficiary could not be found. Please try again."),
                parse_mode=ParseMode.HTML,
            )
            return BENEFICIARY_SELECT

        transaction_state['address'] = beneficiary['address']
        transaction_state['beneficiary_alias'] = beneficiary['alias']

        cancel_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
        )
        await _send_prompt(
            query.message,
            (
                f"📇 <b>{escape_html(beneficiary['alias'])}</b> selected.\n\n"
                "How much XRP would you like to send?"
            ),
            reply_markup=cancel_markup,
            edit=True,
        )
        return AMOUNT

    return BENEFICIARY_SELECT


async def beneficiary_add_alias_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect alias for a new beneficiary."""
    if not update.message or not update.message.text or context.user_data is None:
        return ConversationHandler.END

    alias = update.message.text.strip()
    if not alias:
        await update.message.reply_text(
            "Alias cannot be empty. Please provide a short name.",
            parse_mode=ParseMode.HTML,
        )
        return BENEFICIARY_ADD_ALIAS

    if len(alias) > 100:
        await update.message.reply_text(
            "Alias is too long. Please keep it under 100 characters.",
            parse_mode=ParseMode.HTML,
        )
        return BENEFICIARY_ADD_ALIAS

    context.user_data.setdefault('beneficiary_add', {})['alias'] = alias

    cancel_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
    )
    await update.message.reply_text(
        "Great! Now send me the XRP address for this beneficiary.",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_markup,
    )
    return BENEFICIARY_ADD_ADDRESS


async def beneficiary_add_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect address for a new beneficiary and save it via the API."""
    if not update.message or not update.message.text or context.user_data is None or not update.effective_user:
        return ConversationHandler.END

    address = update.message.text.strip()
    if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
        await update.message.reply_text(
            "Invalid address format. XRP addresses start with 'r'. Please try again.",
            parse_mode=ParseMode.HTML,
        )
        return BENEFICIARY_ADD_ADDRESS

    pending_data = context.user_data.get('beneficiary_add') or {}
    alias = pending_data.get('alias')
    if not alias:
        await update.message.reply_text(
            format_error_message("Alias information missing. Please start again."),
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END

    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
            headers = {"X-API-Key": api_key}
            response = await client.post(
                f"{api_url}/api/v1/beneficiaries/{update.effective_user.id}",
                json={"alias": alias, "address": address},
                headers=headers,
                timeout=20.0,
            )
    except Exception as exc:
        await update.message.reply_text(
            format_error_message(f"Could not save beneficiary: {str(exc)}"),
            parse_mode=ParseMode.HTML,
        )
        return BENEFICIARY_ADD_ADDRESS

    if response.status_code >= 400:
        error_detail = ""
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict):
                error_detail = str(error_payload.get('detail') or error_payload.get('error') or "")
        except ValueError:
            error_detail = response.text

        error_text = error_detail or "Unable to save beneficiary."
        await update.message.reply_text(
            format_error_message(error_text),
            parse_mode=ParseMode.HTML,
        )
        return BENEFICIARY_ADD_ADDRESS

    data = response.json() if response.content else {}
    beneficiary_id = str(data.get('id', ''))
    saved_alias = data.get('alias', alias)
    saved_address = data.get('address', address)

    beneficiary_map = context.user_data.setdefault('beneficiaries', {})
    if beneficiary_id:
        beneficiary_map[beneficiary_id] = {
            "alias": saved_alias,
            "address": saved_address,
        }

    transaction_state = context.user_data.setdefault('transaction', {})
    transaction_state['address'] = saved_address
    transaction_state['beneficiary_alias'] = saved_alias

    context.user_data.pop('beneficiary_add', None)

    cancel_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]]
    )
    await update.message.reply_text(
        (
            f"✅ Beneficiary <b>{escape_html(saved_alias)}</b> saved!\n\n"
            "How much XRP would you like to send?"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_markup,
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

        transaction_state = context.user_data.setdefault('transaction', {})
        transaction_state['amount'] = amount

        if transaction_state.get('address'):
            keyboard = [[KeyboardButton("✅ YES"), KeyboardButton("❌ NO")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

            fee = 0.00001  # Standard fee
            message = format_transaction_confirmation(transaction_state['address'], amount, fee)
            alias = transaction_state.get('beneficiary_alias')
            if alias:
                message = f"📇 <b>Beneficiary:</b> {escape_html(alias)}\n\n" + message

            await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return CONFIRM

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
    
    transaction_state = context.user_data.setdefault('transaction', {})
    transaction_state['address'] = address
    transaction_state.pop('beneficiary_alias', None)
    amount = transaction_state.get('amount', 0)

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
            if response.status_code >= 400:
                await processing_msg.delete()

                error_detail = ""
                try:
                    response_json = response.json()
                    if isinstance(response_json, dict):
                        error_detail = str(
                            response_json.get("detail")
                            or response_json.get("error")
                            or ""
                        )
                except ValueError:
                    error_detail = ""

                if response.status_code == 402:
                    reason_text = (
                        f"Reason: <code>{escape_html(error_detail)}</code>\n\n"
                        if error_detail
                        else ""
                    )
                    low_funds_message = (
                        f"{reason_text}Your available balance is too low to complete this transaction. "
                        "XRPL accounts must keep <b>10 XRP</b> reserved at all times.\n\n"
                        "Visit the <a href='https://test.bithomp.com/en/faucet'>XRPL Testnet Faucet</a> to top up your funds, then try again."
                    )
                    await update.message.reply_text(
                        format_warning_message("Insufficient Funds", low_funds_message),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False,
                    )
                else:
                    error_text = error_detail or f"HTTP {response.status_code}"
                    await update.message.reply_text(
                        format_error_message(f"Transaction Failed\n\nReason: {error_text}"),
                        parse_mode=ParseMode.HTML,
                    )
                return ConversationHandler.END

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
        context.user_data.pop("transaction", None)
        context.user_data.pop("beneficiaries", None)
        context.user_data.pop("beneficiary_add", None)

        # 👉 Always show main menu at the end
        await update.message.reply_text(
            "🏠 <b>Main Menu</b>\n\nWhat would you like to do?",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.main_menu(),
        )
    
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
        context.user_data.pop('beneficiaries', None)
        context.user_data.pop('beneficiary_add', None)
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
