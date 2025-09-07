# bot/handlers/transaction.py
from telegram import Update, ParseMode, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
import httpx
import re

# Conversation states
AMOUNT, ADDRESS, CONFIRM = range(3)

# Store transaction data temporarily (in production, use Redis or database)
transaction_data = {}

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /send command - Start send transaction flow"""
    user_id = update.effective_user.id
    
    # Parse command arguments
    args = context.args
    
    if len(args) == 2:
        # Format: /send [amount] [address]
        try:
            amount = float(args[0])
            address = args[1]
            
            # Validate amount
            if amount <= 0:
                await update.message.reply_text(
                    "❌ *Invalid Amount*\n\n"
                    "Please enter a valid positive number.\n"
                    "Example: `/send 10 rN7n7...`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # Validate address format
            if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
                await update.message.reply_text(
                    "❌ *Invalid Address*\n\n"
                    "The XRP address you entered is invalid.\n"
                    "XRP addresses start with 'r' and are 25-34 characters.\n\n"
                    "Example: `rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # Store transaction data
            transaction_data[user_id] = {
                'amount': amount,
                'address': address
            }
            
            # Ask for confirmation
            keyboard = [
                [KeyboardButton("✅ YES"), KeyboardButton("❌ NO")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                f"📤 *Confirm Transaction*\n\n"
                f"*To:* `{address}`\n"
                f"*Amount:* {amount} XRP\n"
                f"*Fee:* 0.00001 XRP\n"
                f"*Total:* {amount + 0.00001} XRP\n\n"
                f"⚠️ _Please review carefully_\n\n"
                f"Reply *YES* to confirm or *NO* to cancel.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            return CONFIRM
            
    else:
        # Interactive mode - ask for amount first
        keyboard = [[KeyboardButton("/cancel")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "💵 *Send XRP*\n\n"
            "How much XRP would you like to send?\n\n"
            "Example: `10`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return AMOUNT

async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle amount input"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        amount = float(text)
        
        if amount <= 0:
            await update.message.reply_text(
                "❌ *Invalid Amount*\n\n"
                "Please enter a valid positive number.",
                parse_mode=ParseMode.MARKDOWN
            )
            return AMOUNT
        
        # Store amount
        if user_id not in transaction_data:
            transaction_data[user_id] = {}
        transaction_data[user_id]['amount'] = amount
        
        # Ask for address
        keyboard = [[KeyboardButton("/cancel")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "📬 *Recipient Address*\n\n"
            "Enter the XRP address to send to:\n\n"
            "Example: `rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        return ADDRESS
        
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid Amount*\n\n"
            "Please enter a valid number.",
            parse_mode=ParseMode.MARKDOWN
        )
        return AMOUNT

async def address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle address input"""
    user_id = update.effective_user.id
    address = update.message.text.strip()
    
    # Validate address format
    if not re.match(r'^r[a-zA-Z0-9]{24,33}$', address):
        await update.message.reply_text(
            "❌ *Invalid Address*\n\n"
            "The XRP address format is invalid.\n"
            "XRP addresses start with 'r' and are 25-34 characters.\n\n"
            "Please try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ADDRESS
    
    # Store address
    transaction_data[user_id]['address'] = address
    
    # Show confirmation
    amount = transaction_data[user_id]['amount']
    
    keyboard = [
        [KeyboardButton("✅ YES"), KeyboardButton("❌ NO")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📤 *Confirm Transaction*\n\n"
        f"*To:* `{address}`\n"
        f"*Amount:* {amount} XRP\n"
        f"*Fee:* 0.00001 XRP\n"
        f"*Total:* {amount + 0.00001} XRP\n\n"
        f"⚠️ _Please review carefully_\n\n"
        f"Reply *YES* to confirm or *NO* to cancel.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return CONFIRM

async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle transaction confirmation"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if "YES" not in text.upper():
        await update.message.reply_text(
            "❌ Transaction cancelled.",
            reply_markup=ReplyKeyboardRemove()
        )
        transaction_data.pop(user_id, None)
        return ConversationHandler.END
    
    # Get transaction details
    if user_id not in transaction_data:
        await update.message.reply_text(
            "❌ Transaction data not found. Please start over with /send",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    tx_data = transaction_data[user_id]
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "⏳ Processing transaction...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    
    try:
        async with httpx.AsyncClient() as client:
            # Send transaction via API
            response = await client.post(
                f"{context.bot_data['api_url']}/api/v1/transaction/send",
                json={
                    "from_telegram_id": str(user_id),
                    "to_address": tx_data['address'],
                    "amount": tx_data['amount']
                },
                timeout=30.0
            )
            
            # Delete processing message
            await processing_msg.delete()
            
            data = response.json()
            
            if data.get("success"):
                message = (
                    "✅ *Transaction Successful!*\n\n"
                    f"*Amount:* {tx_data['amount']} XRP\n"
                    f"*To:* `{tx_data['address']}`\n"
                    f"*Fee:* {data.get('fee', 0.00001)} XRP\n\n"
                    f"*Transaction Hash:*\n`{data.get('tx_hash')}`\n\n"
                    f"View on explorer:\n"
                    f"https://testnet.xrpl.org/transactions/{data.get('tx_hash')}"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
            else:
                error = data.get('error', 'Unknown error')
                
                await update.message.reply_text(
                    f"❌ *Transaction Failed*\n\n"
                    f"*Reason:* {error}\n\n"
                    "Please check your balance and try again.\n"
                    "Use /balance to check your current balance.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(
            f"❌ *Transaction Failed*\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    finally:
        # Clear transaction data
        transaction_data.pop(user_id, None)
    
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancellation"""
    user_id = update.effective_user.id
    transaction_data.pop(user_id, None)
    
    await update.message.reply_text(
        "❌ Transaction cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END

