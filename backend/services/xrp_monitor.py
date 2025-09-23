"""XRP Ledger transaction monitoring service for incoming payments."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import Subscribe

from ..config import settings
from ..database.connection import get_db_session
from ..database.models import User, Wallet

logger = logging.getLogger(__name__)


class XRPTransactionMonitor:
    """Service for monitoring incoming XRP transactions to user wallets."""

    def __init__(self) -> None:
        """Initialize the XRP transaction monitor."""
        self.client: AsyncWebsocketClient | None = None
        self.subscribed_addresses: set[str] = set()
        self.running = False
        self._monitor_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the XRP transaction monitoring service."""
        if self.running:
            logger.warning("XRP monitor is already running")
            return

        try:
            logger.info("Starting XRP transaction monitor...")

            # Connect to XRP Ledger WebSocket
            self.client = AsyncWebsocketClient(settings.XRP_WEBSOCKET_URL)
            await self.client.open()

            # Subscribe to all user wallet addresses
            await self._subscribe_to_user_wallets()

            self.running = True
            logger.info("✅ XRP transaction monitor started successfully")

            # Start listening for transactions in background
            self._monitor_task = asyncio.create_task(self._listen_for_transactions())

        except Exception as e:
            logger.error(f"❌ Failed to start XRP transaction monitor: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the XRP transaction monitoring service."""
        self.running = False

        # Cancel monitoring task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self.client:
            try:
                await self.client.close()
                logger.info("✅ XRP transaction monitor stopped")
            except Exception as e:
                logger.error(f"Error stopping XRP monitor: {e}")
            finally:
                self.client = None

        self.subscribed_addresses.clear()

    async def _subscribe_to_user_wallets(self) -> None:
        """Subscribe to all user wallet addresses for transaction monitoring."""
        if not self.client:
            msg = "XRP client not connected"
            raise RuntimeError(msg)

        db = get_db_session()
        try:
            # Get all active user wallets
            wallets = db.query(Wallet).join(User).filter(User.is_active == True).all()  # noqa: E712

            addresses = [str(wallet.xrp_address) for wallet in wallets]

            if not addresses:
                logger.info("No user wallets to monitor")
                return

            # Subscribe to account transactions for all addresses
            subscription = Subscribe(accounts=addresses)

            response = await self.client.request(subscription)

            if response.is_successful():
                self.subscribed_addresses.update(addresses)
                logger.info(
                    f"✅ Subscribed to {len(addresses)} wallet addresses with transaction stream"
                )
                # Log the actual addresses for debugging
                for addr in addresses:
                    logger.info(f"   📍 Monitoring: {addr}")
            else:
                logger.error(f"Failed to subscribe to wallets: {response.result}")

        except Exception as e:
            logger.error(f"Error subscribing to user wallets: {e}")
            raise
        finally:
            db.close()

    async def add_wallet_subscription(self, address: str) -> None:
        """Add a new wallet address to the monitoring subscription."""
        if not self.client or not self.running:
            logger.warning(f"Cannot add wallet {address} - monitor not running")
            return

        if address in self.subscribed_addresses:
            logger.debug(f"Wallet {address} already subscribed")
            return

        try:
            # Subscribe to this specific address
            subscription = Subscribe(accounts=[address])
            response = await self.client.request(subscription)

            if response.is_successful():
                self.subscribed_addresses.add(address)
                logger.info(f"✅ Added wallet {address} to monitoring with transaction stream")
            else:
                logger.error(f"Failed to subscribe to wallet {address}: {response.result}")

        except Exception as e:
            logger.error(f"Error adding wallet subscription for {address}: {e}")

    async def _listen_for_transactions(self) -> None:
        """Listen for incoming transaction notifications."""
        if not self.client:
            msg = "XRP client not connected"
            raise RuntimeError(msg)

        logger.info("🔄 Listening for incoming XRP transactions...")
        message_count = 0

        try:
            async for message in self.client:
                if not self.running:
                    break

                message_count += 1
                if message_count % 10 == 0:  # Log every 10 messages
                    logger.info(f"Processed {message_count} WebSocket messages")

                try:
                    await self._process_transaction_message(message)
                except Exception as e:
                    logger.error(f"Error processing transaction message: {e}", exc_info=True)
        except asyncio.CancelledError:
            logger.info("Transaction monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in transaction listener: {e}", exc_info=True)
            # Try to reconnect on connection errors
            if "connection" in str(e).lower() or "websocket" in str(e).lower():
                logger.info("Attempting to reconnect WebSocket...")
                await self.stop()
                await asyncio.sleep(5)  # Wait before reconnecting
                await self.start()

    async def _process_transaction_message(self, message: dict[str, Any]) -> None:
        """Process an incoming transaction message from XRP Ledger."""
        try:
            # Only process transaction messages
            if message.get("type") != "transaction":
                return

            transaction = message.get("transaction", {})
            meta = message.get("meta", {})

            # Skip if no transaction data
            if not transaction or not meta:
                return

            tx_type = transaction.get("TransactionType")
            tx_result = meta.get("TransactionResult")

            # Only process successful Payment transactions
            if tx_type != "Payment" or tx_result != "tesSUCCESS":
                return

            # Extract transaction details
            destination = transaction.get("Destination")
            # Try DeliverMax first (newer transactions), then fallback to Amount
            amount = transaction.get("DeliverMax") or transaction.get("Amount")
            sender = transaction.get("Account")
            tx_hash = transaction.get("hash")

            # Skip if destination is not one of our monitored addresses
            if destination not in self.subscribed_addresses:
                return

            # Convert amount from drops to XRP (if it's a string)
            if isinstance(amount, str):
                xrp_amount = float(amount) / 1_000_000  # Convert drops to XRP
            else:
                # Handle non-XRP currencies (for future expansion)
                logger.debug(f"Received non-XRP payment: {amount}")
                return

            logger.info(
                f"💰 Incoming XRP payment detected: {xrp_amount} XRP to {destination} "
                f"from {sender} (TX: {tx_hash})"
            )

            # Send notification to the user
            await self._notify_user_of_incoming_payment(
                recipient_address=destination,
                sender_address=sender,
                amount=xrp_amount,
                tx_hash=tx_hash,
            )

        except Exception as e:
            logger.error(f"Error processing transaction message: {e}", exc_info=True)

    async def _notify_user_of_incoming_payment(
        self,
        recipient_address: str,
        sender_address: str,
        amount: float,
        tx_hash: str,
    ) -> None:
        """Send a notification to the user about an incoming XRP payment."""
        db = get_db_session()
        try:
            # Find the user who owns this wallet
            wallet = db.query(Wallet).filter(Wallet.xrp_address == recipient_address).first()

            if not wallet or not wallet.user:
                logger.warning(f"No user found for wallet address {recipient_address}")
                return

            user = wallet.user

            # Check if user has notifications enabled
            if user.settings and not user.settings.transaction_notifications:
                logger.debug(f"User {user.telegram_id} has transaction notifications disabled")
                return

            # Format the notification message
            message = (
                f"💰 <b>Incoming XRP Payment</b>\n\n"
                f"<b>Amount:</b> {amount:.6f} XRP\n"
                f"<b>From:</b> <code>{sender_address}</code>\n"
                f"<b>To:</b> <code>{recipient_address}</code>\n"
                f"<b>Transaction:</b> <code>{tx_hash}</code>\n\n"
                f"🎉 Your wallet balance has been updated!"
            )

            # Send notification using the appropriate method for the environment
            await self._send_notification_to_user(user.telegram_id, message)

            logger.info(f"✅ Notification sent to user {user.telegram_id} for incoming payment")

            # Update wallet balance cache
            from .xrp_service import xrp_service

            new_balance = await xrp_service.get_balance(recipient_address)
            if new_balance is not None:
                wallet.balance = new_balance
                wallet.last_balance_update = datetime.now(timezone.utc)
                db.commit()
                logger.debug(f"Updated cached balance for {recipient_address}: {new_balance} XRP")

        except Exception as e:
            logger.error(f"Error notifying user of incoming payment: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    async def _send_notification_to_user(self, telegram_id: str, message: str) -> None:
        """Send notification to user, handling both dev (polling) and prod (webhook) modes."""
        try:
            # Check if we're in webhook mode (production) or polling mode (development)
            from ..main import telegram_app_instance

            if telegram_app_instance:
                # Production/webhook mode - use the existing app instance
                await telegram_app_instance.bot.send_message(
                    chat_id=int(telegram_id), text=message, parse_mode="HTML"
                )
            else:
                # Development/polling mode - create a temporary bot instance
                from telegram import Bot

                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

                try:
                    await bot.initialize()
                    await bot.send_message(
                        chat_id=int(telegram_id), text=message, parse_mode="HTML"
                    )
                finally:
                    await bot.shutdown()

        except Exception as e:
            logger.error(f"Failed to send notification to user {telegram_id}: {e}")
            raise


# Global monitor instance
xrp_monitor = XRPTransactionMonitor()


async def start_xrp_monitoring() -> None:
    """Start XRP transaction monitoring service."""
    try:
        await xrp_monitor.start()
    except Exception as e:
        logger.error(f"Failed to start XRP monitoring: {e}")


async def stop_xrp_monitoring() -> None:
    """Stop XRP transaction monitoring service."""
    try:
        await xrp_monitor.stop()
    except Exception as e:
        logger.error(f"Failed to stop XRP monitoring: {e}")


async def add_wallet_to_monitoring(address: str) -> None:
    """Add a new wallet address to monitoring."""
    try:
        await xrp_monitor.add_wallet_subscription(address)
    except Exception as e:
        logger.error(f"Failed to add wallet {address} to monitoring: {e}")


async def refresh_wallet_subscriptions() -> None:
    """Refresh all wallet subscriptions to include any missing wallets."""
    try:
        if xrp_monitor.running:
            await xrp_monitor._subscribe_to_user_wallets()
        else:
            logger.warning("XRP monitor not running - cannot refresh subscriptions")
    except Exception as e:
        logger.error(f"Failed to refresh wallet subscriptions: {e}")
