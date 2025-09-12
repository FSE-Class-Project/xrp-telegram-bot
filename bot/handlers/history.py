# bot/handlers/history.py
"""Transaction history handlers with pagination."""

from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
import logging
from datetime import datetime

from ..utils.formatting import (
    escape_html,
    format_error_message,
    format_success_message,
)

logger = logging.getLogger(__name__)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command."""
    await show_transaction_history(update, context, page=0)


async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Show transaction history with pagination."""
    user = update.effective_user
    if not user:
        return
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Calculate offset and limit
        limit = 5  # Show 5 transactions per page
        offset = page * limit
        
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/transaction/history/{user.id}?limit={limit}&offset={offset}",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                transactions = data.get('transactions', [])
                total_count = data.get('total_count', 0)
                
                if not transactions and page == 0:
                    message = """
📊 <b>Transaction History</b>

💼 <i>No transactions found.</i>

You haven't made any transactions yet. Start by sending some XRP!

<b>Quick Actions:</b>
• Use /send to make your first transaction
• Use /balance to check your current balance
"""
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("💸 Send XRP", callback_data="send_xrp"),
                            InlineKeyboardButton("💰 Balance", callback_data="balance")
                        ],
                        [InlineKeyboardButton("🔙 Back", callback_data="back")]
                    ])
                    
                elif not transactions and page > 0:
                    # No more transactions on this page
                    await show_transaction_history(update, context, page - 1)
                    return
                    
                else:
                    # Format transactions
                    message = format_transaction_history(transactions, page, total_count, limit)
                    keyboard = create_history_pagination_keyboard(page, total_count, limit)
                
            else:
                from ..utils.formatting import format_warning_message
                message = format_warning_message(
                    "History Unavailable",
                    "Could not load your transaction history. Please try again later."
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data="history")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back")]
                ])
            
            if update.message:
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
                
    except Exception as e:
        logger.error(f"Error in show_transaction_history: {e}", exc_info=True)
        error_message = format_error_message(
            "An error occurred while loading transaction history."
        )
        
        if update.message:
            await update.message.reply_text(error_message, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.answer("History error", show_alert=True)


async def history_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle history pagination."""
    query = update.callback_query
    if not query or not query.data:
        return
    
    try:
        # Extract page number from callback data
        page = int(query.data.split('_')[2])  # Format: history_page_N
        await show_transaction_history(update, context, page)
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing history page: {e}")
        await query.answer("Invalid page number", show_alert=True)


def format_transaction_history(transactions: List[Dict[str, Any]], page: int, total_count: int, limit: int) -> str:
    """Format transaction history for display."""
    start_index = page * limit + 1
    end_index = min((page + 1) * limit, total_count)
    
    message = f"""
📊 <b>Transaction History</b>

<b>Showing {start_index}-{end_index} of {total_count} transactions</b>

"""
    
    for i, tx in enumerate(transactions):
        # Format status emoji
        status = tx.get('status', 'unknown')
        if status == 'confirmed':
            status_emoji = '✅'
        elif status == 'pending':
            status_emoji = '⏳'
        elif status == 'failed':
            status_emoji = '❌'
        else:
            status_emoji = '❓'
        
        # Format timestamp
        timestamp = tx.get('timestamp')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%m/%d %H:%M')
            except:
                formatted_time = timestamp[:16].replace('T', ' ')
        else:
            formatted_time = 'Unknown'
        
        # Format transaction
        amount = tx.get('amount', 0)
        recipient = tx.get('recipient', 'Unknown')
        tx_hash = tx.get('hash', 'N/A')
        
        # Truncate recipient address
        if len(recipient) > 20:
            recipient_short = f"{recipient[:8]}...{recipient[-8:]}"
        else:
            recipient_short = recipient
        
        # Truncate hash
        if tx_hash and tx_hash != 'N/A' and len(tx_hash) > 16:
            hash_short = f"{tx_hash[:8]}...{tx_hash[-8:]}"
        else:
            hash_short = tx_hash or 'N/A'
        
        message += f"""
{status_emoji} <b>Transaction #{start_index + i}</b>
💰 Amount: {amount:.6f} XRP
📍 To: <code>{recipient_short}</code>
🏷️ Hash: <code>{hash_short}</code>
🕐 Time: {formatted_time}
"""
        
        # Add error message if failed
        if status == 'failed' and tx.get('error'):
            error_msg = tx['error'][:50] + ('...' if len(tx['error']) > 50 else '')
            message += f"❗ Error: <i>{escape_html(error_msg)}</i>\n"
        
        message += "\n"
    
    message += "<i>💡 Tap a transaction hash to view on XRP Ledger explorer</i>"
    
    return message


def create_history_pagination_keyboard(page: int, total_count: int, limit: int) -> InlineKeyboardMarkup:
    """Create pagination keyboard for transaction history."""
    total_pages = (total_count + limit - 1) // limit  # Ceiling division
    
    keyboard = []
    
    # Navigation buttons
    nav_row = []
    
    # Previous page button
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"history_page_{page - 1}"))
    
    # Page indicator
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="page_info"))
    
    # Next page button
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"history_page_{page + 1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Quick navigation for multiple pages
    if total_pages > 3:
        quick_nav = []
        
        # First page
        if page > 1:
            quick_nav.append(InlineKeyboardButton("1", callback_data="history_page_0"))
        
        # Current page - 1 (if applicable)
        if page > 2:
            quick_nav.append(InlineKeyboardButton(f"{page}", callback_data=f"history_page_{page - 1}"))
        
        # Current page + 1 (if applicable)
        if page < total_pages - 2:
            quick_nav.append(InlineKeyboardButton(f"{page + 2}", callback_data=f"history_page_{page + 1}"))
        
        # Last page
        if page < total_pages - 2:
            quick_nav.append(InlineKeyboardButton(f"{total_pages}", callback_data=f"history_page_{total_pages - 1}"))
        
        if quick_nav:
            keyboard.append(quick_nav)
    
    # Action buttons
    keyboard.extend([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"history_page_{page}"),
            InlineKeyboardButton("📊 Export", callback_data="export_data")
        ],
        [
            InlineKeyboardButton("💸 Send XRP", callback_data="send_xrp"),
            InlineKeyboardButton("💰 Balance", callback_data="balance")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ])
    
    return InlineKeyboardMarkup(keyboard)


async def transaction_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed transaction information."""
    query = update.callback_query
    if not query or not query.data:
        return
    
    await query.answer()
    
    try:
        # Extract transaction hash from callback data
        tx_hash = query.data.split('_')[2]  # Format: tx_details_HASH
        
        user = update.effective_user
        if not user:
            return
        
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Fetch transaction details
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/transaction/{tx_hash}",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                tx = response.json()
                
                # Format detailed transaction view
                message = f"""
🔍 <b>Transaction Details</b>

<b>Basic Info:</b>
💰 Amount: {tx.get('amount', 0):.6f} XRP
💸 Fee: {tx.get('fee', 0):.6f} XRP
📊 Status: {tx.get('status', 'Unknown').title()}

<b>Addresses:</b>
📤 From: <code>{tx.get('sender_address', 'N/A')}</code>
📥 To: <code>{tx.get('recipient_address', 'N/A')}</code>

<b>Network Info:</b>
🏷️ Hash: <code>{tx.get('hash', 'N/A')}</code>
🔗 Ledger: {tx.get('ledger_index', 'N/A')}

<b>Timing:</b>
⏰ Created: {tx.get('timestamp', 'N/A')[:19].replace('T', ' ')}
{f"✅ Confirmed: {tx.get('confirmed_at', 'N/A')[:19].replace('T', ' ')}" if tx.get('confirmed_at') else '⏳ Pending confirmation'}

"""
                
                if tx.get('status') == 'failed' and tx.get('error'):
                    message += f"\n❌ <b>Error:</b> {escape_html(tx['error'])}"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 View on Explorer", url=f"https://testnet.xrpl.org/transactions/{tx.get('hash', '')}")],
                    [
                        InlineKeyboardButton("🔙 Back to History", callback_data="history"),
                        InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                    ]
                ])
                
                await query.edit_message_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                await query.answer("Transaction not found", show_alert=True)
                
    except Exception as e:
        logger.error(f"Error in transaction_details: {e}", exc_info=True)
        await query.answer("Failed to load transaction details", show_alert=True)
