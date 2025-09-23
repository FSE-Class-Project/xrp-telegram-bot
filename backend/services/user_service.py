"""User service with proper typing and model returns."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc  # Import desc directly
from sqlalchemy.orm import Session

from ..constants import STANDARD_FEE

# Use relative imports for consistency
from ..database.models import (
    Beneficiary,
    Transaction,
    User,
    UserSettings,
    Wallet,
)
from .cache_service import get_cache_service
from .xrp_service import xrp_service

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users and wallets."""

    def __init__(self) -> None:
        """Initialize user service with cache."""
        self.cache = get_cache_service()

    async def create_user(
        self,
        db: Session,
        telegram_id: str,
        telegram_username: str | None = None,
        telegram_first_name: str | None = None,
        telegram_last_name: str | None = None,
        auto_fund: bool = True,
    ) -> User:
        """Create a new user with an XRP wallet.

        Returns a User model instance, not a dictionary.
        """
        # Check cache first
        cached_user = self.cache.get_user(telegram_id)
        if cached_user and cached_user.get("id"):
            # Verify user still exists in database
            existing_user = db.query(User).filter(User.id == cached_user["id"]).first()
            if existing_user:
                return existing_user

        # Check if user already exists
        existing_user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()

        if existing_user:
            return existing_user

        # Create new user
        user = User(
            telegram_id=str(telegram_id),
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            telegram_last_name=telegram_last_name,
        )

        db.add(user)
        db.flush()  # Get user ID without committing

        # Invalidate cache for this telegram ID
        self.cache.invalidate_user(telegram_id)

        # Create XRP wallet
        address, encrypted_secret = xrp_service.create_wallet()

        wallet = Wallet(
            user_id=user.id,
            xrp_address=address,
            encrypted_secret=encrypted_secret,
            balance=0.0,
        )

        db.add(wallet)

        # Create default settings
        settings = UserSettings(user_id=user.id)
        db.add(settings)

        db.commit()
        db.refresh(user)

        # Cache the new user data
        self._cache_user_data(user)

        # Fund wallet from faucet if requested (async operation)
        if auto_fund:
            try:
                logger.info(f"Attempting to fund wallet {address} with TestNet XRP")
                funded = await xrp_service.fund_wallet_from_faucet(address)
                if funded:
                    # Wait a moment for the transaction to settle
                    import asyncio

                    await asyncio.sleep(3)

                    # Update balance
                    balance = await xrp_service.get_balance(address)
                    if balance is not None:
                        # Update wallet balance properly
                        wallet_obj = db.query(Wallet).filter(Wallet.user_id == user.id).first()
                        if wallet_obj:
                            wallet_obj.balance = balance
                            wallet_obj.last_balance_update = datetime.now(timezone.utc)
                            db.commit()
                            db.refresh(user)  # Refresh to get updated wallet
                            logger.info(f"Wallet funded successfully. New balance: {balance} XRP")
                    else:
                        logger.warning("Faucet funding reported success but balance is still None")
                else:
                    logger.warning("Faucet funding failed - wallet will remain unfunded")
            except Exception as e:
                logger.error(f"Error funding wallet: {str(e)}")
        else:
            logger.info(f"Auto-funding disabled for wallet {address}")

        # Add wallet to XRP monitoring
        try:
            from .xrp_monitor import add_wallet_to_monitoring

            await add_wallet_to_monitoring(address)
            logger.info(f"Added wallet {address} to XRP monitoring")
        except Exception as e:
            logger.error(f"Failed to add wallet {address} to monitoring: {e}")

        return user  # Return User model instance

    async def create_or_get_user(
        self,
        db: Session,
        telegram_id: str,
        telegram_username: str | None = None,
        telegram_first_name: str | None = None,
        telegram_last_name: str | None = None,
    ) -> User:
        """Get existing user or create new one.

        Returns a User model instance.
        """
        existing_user = self.get_user_by_telegram_id(db, telegram_id)
        if existing_user:
            return existing_user

        return await self.create_user(
            db=db,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            telegram_last_name=telegram_last_name,
        )

    async def create_user_with_wallet(
        self,
        db: Session,
        telegram_id: str,
        telegram_username: str | None = None,
        telegram_first_name: str | None = None,
        telegram_last_name: str | None = None,
        xrp_address: str | None = None,
        encrypted_secret: str | None = None,
    ) -> User:
        """Create a new user with an existing wallet.

        Args:
        ----
            db: Database session
            telegram_id: Telegram user ID
            telegram_username: Telegram username
            telegram_first_name: Telegram first name
            telegram_last_name: Telegram last name
            xrp_address: XRP wallet address
            encrypted_secret: Encrypted wallet secret

        Returns:
        -------
            User: Created user with wallet

        """
        # Check if user already exists
        existing_user = self.get_user_by_telegram_id(db, telegram_id)
        if existing_user:
            logger.info(f"User {telegram_id} already exists, updating wallet")
            return existing_user

        # Create user
        user = User(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            telegram_last_name=telegram_last_name,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Invalidate cache for this telegram ID
        self.cache.invalidate_user(telegram_id)

        # Create wallet with provided data
        wallet = Wallet(
            user_id=user.id,
            xrp_address=xrp_address,
            encrypted_secret=encrypted_secret,
            balance=0.0,
        )

        db.add(wallet)

        # Create default settings
        settings = UserSettings(user_id=user.id)
        db.add(settings)

        db.commit()
        db.refresh(user)

        # Cache the new user data
        self._cache_user_data(user)

        # Add wallet to XRP monitoring
        if xrp_address:
            try:
                from .xrp_monitor import add_wallet_to_monitoring

                await add_wallet_to_monitoring(xrp_address)
                logger.info(f"Added wallet {xrp_address} to XRP monitoring")
            except Exception as e:
                logger.error(f"Failed to add wallet {xrp_address} to monitoring: {e}")

        logger.info(f"Created user {telegram_id} with imported wallet {xrp_address}")

        return user

    def _cache_user_data(self, user: User) -> None:
        """Cache user and wallet data."""
        if not user:
            return

        # Cache user data
        user_data = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "telegram_first_name": user.telegram_first_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        self.cache.set_user(str(user.telegram_id), user_data)

        # Cache wallet data if exists
        if user.wallet:
            wallet_data = {
                "id": user.wallet.id,
                "user_id": user.wallet.user_id,
                "xrp_address": user.wallet.xrp_address,
                "balance": user.wallet.balance,
                "last_balance_update": (
                    user.wallet.last_balance_update.isoformat()
                    if user.wallet.last_balance_update
                    else None
                ),
            }
            self.cache.set_wallet(int(user.id), wallet_data)

    def get_user_by_telegram_id(self, db: Session, telegram_id: str) -> User | None:
        """Get user by Telegram ID.

        Returns a User model instance or None.
        """
        # Check cache first
        cached_user = self.cache.get_user(telegram_id)
        if cached_user and cached_user.get("id"):
            # Get full user from database using cached ID
            user = db.query(User).filter(User.id == cached_user["id"]).first()
            if user:
                return user
            else:
                # Invalidate stale cache
                self.cache.invalidate_user(telegram_id)

        # Query database
        user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()

        # Cache the result if found
        if user:
            self._cache_user_data(user)

        return user

    def get_user_by_xrp_address(self, db: Session, xrp_address: str) -> User | None:
        """Get user by XRP address.

        Returns a User model instance or None.
        """
        wallet = db.query(Wallet).filter(Wallet.xrp_address == xrp_address).first()

        return wallet.user if wallet else None

    async def update_balance(self, db: Session, user: User) -> float:
        """Update user's wallet balance from blockchain.

        Returns the updated balance as float.
        """
        if not user.wallet:
            raise ValueError("User has no wallet")

        # Get balance from XRP Ledger
        balance = await xrp_service.get_balance(user.wallet.xrp_address)

        if balance is not None:
            # Update wallet balance properly
            wallet_instance = user.wallet
            if wallet_instance:
                wallet_instance.balance = balance
                wallet_instance.last_balance_update = datetime.now(timezone.utc)
                db.commit()
                db.refresh(user)

        return float(
            balance if balance is not None else (user.wallet.balance if user.wallet else 0.0)
        )

    async def send_xrp(
        self,
        db: Session,
        sender: User,
        recipient_address: str,
        amount: float,
        memo: str | None = None,
    ) -> dict[str, Any]:
        """Send XRP from user to another address.

        Returns a dictionary with transaction results.
        """
        if not sender.wallet:
            return {"success": False, "error": "Sender has no wallet"}

        # Validate recipient address
        if not xrp_service.validate_address(recipient_address):
            return {"success": False, "error": "Invalid recipient address"}

        # Check if recipient is internal user
        recipient_wallet = db.query(Wallet).filter(Wallet.xrp_address == recipient_address).first()

        # Send transaction
        result = await xrp_service.send_xrp(
            from_encrypted_secret=sender.wallet.encrypted_secret,
            to_address=recipient_address,
            amount=amount,
            memo=memo,
        )

        if result["success"]:
            # Record transaction
            transaction = Transaction(
                sender_id=sender.id,
                sender_address=sender.wallet.xrp_address,
                recipient_address=recipient_address,
                amount=amount,
                fee=result.get("fee", float(STANDARD_FEE)),
                tx_hash=result.get("tx_hash"),
                ledger_index=result.get("ledger_index"),
                status="confirmed",
                confirmed_at=datetime.now(timezone.utc),
            )
            db.add(transaction)

            # Update balances
            await self.update_balance(db, sender)

            # If internal transfer, update recipient balance too
            if recipient_wallet and recipient_wallet.user:  # Add check for user
                recipient_user = recipient_wallet.user
                await self.update_balance(db, recipient_user)

            db.commit()
        else:
            # Record failed transaction
            transaction = Transaction(
                sender_id=sender.id,
                sender_address=sender.wallet.xrp_address,
                recipient_address=recipient_address,
                amount=amount,
                status="failed",
                error_message=result.get("error"),
            )
            db.add(transaction)
            db.commit()

        return result

    def get_beneficiaries(self, db: Session, user: User) -> list[Beneficiary]:
        """Retrieve all beneficiaries for a user ordered by alias."""
        if not user.id:
            return []

        return (
            db.query(Beneficiary)
            .filter(Beneficiary.user_id == user.id)
            .order_by(Beneficiary.alias.asc())
            .all()
        )

    def add_beneficiary(self, db: Session, user: User, alias: str, address: str) -> Beneficiary:
        """Create a new beneficiary for quick sends."""
        if not user.id:
            raise ValueError("User must be persisted before adding beneficiaries")

        cleaned_alias = alias.strip()
        if not cleaned_alias:
            raise ValueError("Alias cannot be empty")

        if len(cleaned_alias) > 100:
            raise ValueError("Alias must be 100 characters or fewer")

        if not xrp_service.validate_address(address):
            raise ValueError("Invalid XRP address format")

        existing_alias = (
            db.query(Beneficiary)
            .filter(
                Beneficiary.user_id == user.id,
                Beneficiary.alias == cleaned_alias,
            )
            .first()
        )
        if existing_alias:
            raise ValueError("You already have a beneficiary with this alias")

        existing_address = (
            db.query(Beneficiary)
            .filter(Beneficiary.user_id == user.id, Beneficiary.address == address)
            .first()
        )
        if existing_address:
            raise ValueError("This address is already saved as a beneficiary")

        beneficiary = Beneficiary(user_id=user.id, alias=cleaned_alias, address=address)
        db.add(beneficiary)
        db.commit()
        db.refresh(beneficiary)
        return beneficiary

    def get_transaction_history(
        self,
        db: Session,
        user: User,
        limit: int = 10,
        offset: int = 0,  # Added offset parameter
    ) -> list[dict[str, Any]]:
        """Get user's transaction history from database.

        Returns a list of transaction dictionaries.
        """
        # Use desc() function directly from sqlalchemy
        transactions = (
            db.query(Transaction)
            .filter(Transaction.sender_id == user.id)
            .order_by(desc(Transaction.created_at))  # Use desc() function
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "hash": tx.tx_hash,
                "amount": tx.amount,
                "fee": tx.fee,
                "recipient": tx.recipient_address,
                "status": tx.status,
                "timestamp": tx.created_at.isoformat() if tx.created_at else None,  # Handle None
                "error": tx.error_message,
            }
            for tx in transactions
        ]

    def get_transaction_count(self, db: Session, user: User) -> int:
        """Get total transaction count for a user."""
        return db.query(Transaction).filter(Transaction.sender_id == user.id).count()


# Global user service instance
user_service = UserService()
