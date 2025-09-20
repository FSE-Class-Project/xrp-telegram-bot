"""Idempotency utilities for preventing duplicate operations."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import IdempotencyRecord, Transaction


class IdempotencyKey:
    """Generate and validate idempotency keys."""

    @staticmethod
    def generate() -> str:
        """Generate a new idempotency key."""
        return str(uuid.uuid4())

    @staticmethod
    def from_request(user_id: int | None, operation: str, data: dict[str, Any]) -> str:
        """Generate deterministic key from request data."""
        # Create a consistent hash from request components
        key_data = {"user_id": user_id, "operation": operation, "data": data}
        # Sort keys for consistent hashing
        key_string = json.dumps(key_data, sort_keys=True)
        hash_obj = hashlib.sha256(key_string.encode())
        return f"{operation}_{hash_obj.hexdigest()[:16]}"

    @staticmethod
    def validate(key: str) -> bool:
        """Validate idempotency key format."""
        if not key or len(key) < 8 or len(key) > 255:
            return False
        # Allow alphanumeric, hyphens, and underscores
        return all(c.isalnum() or c in "-_" for c in key)


class IdempotencyManager:
    """Manage idempotency records and prevent duplicate operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_request_hash(self, data: dict[str, Any]) -> str:
        """Create SHA256 hash of request data."""
        # Normalize and sort data for consistent hashing
        normalized_data = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(normalized_data.encode()).hexdigest()

    async def check_idempotency(
        self,
        idempotency_key: str,
        user_id: int | None,  # noqa: ARG002
        operation_type: str,  # noqa: ARG002
        request_data: dict[str, Any],
        ttl_hours: int = 24,  # noqa: ARG002
    ) -> IdempotencyRecord | None:
        """Check if operation already exists and return existing record if found.

        Returns
        -------
            IdempotencyRecord if duplicate request found, None if new request

        """
        if not IdempotencyKey.validate(idempotency_key):
            raise ValueError("Invalid idempotency key format")

        # Check for existing record
        existing = (
            self.db.query(IdempotencyRecord)
            .filter(IdempotencyRecord.idempotency_key == idempotency_key)
            .first()
        )

        if existing:
            # Check if record has expired
            if existing.expires_at <= datetime.now(timezone.utc):
                # Remove expired record and allow new request
                self.db.delete(existing)
                self.db.commit()
                return None

            # Verify request data matches (prevent key collision attacks)
            request_hash = self.create_request_hash(request_data)
            if existing.request_hash != request_hash:
                raise ValueError("Idempotency key collision detected")

            return existing

        return None

    async def create_idempotency_record(
        self,
        idempotency_key: str,
        user_id: int | None,
        operation_type: str,
        request_data: dict[str, Any],
        ttl_hours: int = 24,
    ) -> IdempotencyRecord:
        """Create new idempotency record for tracking."""
        request_hash = self.create_request_hash(request_data)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            user_id=user_id,
            operation_type=operation_type,
            request_hash=request_hash,
            request_data=json.dumps(request_data),
            response_status="processing",
            expires_at=expires_at,
        )

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            return record
        except IntegrityError:
            self.db.rollback()
            # Race condition - record was created by another request
            existing = await self.check_idempotency(
                idempotency_key,
                user_id,
                operation_type,
                request_data,
                ttl_hours,
            )
            if existing:
                return existing
            raise

    async def update_idempotency_record(
        self,
        record: IdempotencyRecord,
        status: str,
        response_data: dict[str, Any] | None = None,
        transaction_id: int | None = None,
    ) -> None:
        """Update idempotency record with operation result."""
        record.response_status = status  # type: ignore[assignment]
        if response_data:
            record.response_data = json.dumps(response_data)  # type: ignore[assignment]
        if transaction_id:
            record.transaction_id = transaction_id  # type: ignore[assignment]

        self.db.commit()

    async def cleanup_expired_records(self, batch_size: int = 1000) -> int:
        """Clean up expired idempotency records."""
        now = datetime.now(timezone.utc)

        # Find expired records
        expired_records = (
            self.db.query(IdempotencyRecord)
            .filter(IdempotencyRecord.expires_at <= now)
            .limit(batch_size)
            .all()
        )

        count = len(expired_records)
        if count > 0:
            # Delete expired records
            for record in expired_records:
                self.db.delete(record)
            self.db.commit()

        return count


class TransactionIdempotency:
    """Specific idempotency handling for transactions."""

    def __init__(self, db: Session):
        self.db = db
        self.manager = IdempotencyManager(db)

    async def check_transaction_idempotency(
        self,
        idempotency_key: str,
        user_id: int,
        to_address: str,
        amount: float,
    ) -> IdempotencyRecord | Transaction | None:
        """Check for duplicate transaction requests.

        Returns
        -------
            IdempotencyRecord if duplicate in progress
            Transaction if completed duplicate
            None if new request

        """
        request_data = {
            "to_address": to_address,
            "amount": str(amount),  # Use string to avoid float precision issues
            "user_id": user_id,
        }

        # Check idempotency record first
        record = await self.manager.check_idempotency(
            idempotency_key, user_id, "send_transaction", request_data
        )

        if record:
            # If record exists and has transaction_id, return the transaction
            if record.transaction_id:
                transaction = (
                    self.db.query(Transaction)
                    .filter(Transaction.id == record.transaction_id)
                    .first()
                )
                if transaction:
                    return transaction
            return record

        return None

    async def create_transaction_idempotency(
        self,
        idempotency_key: str,
        user_id: int,
        to_address: str,
        amount: float,
    ) -> IdempotencyRecord:
        """Create idempotency record for new transaction."""
        request_data = {
            "to_address": to_address,
            "amount": str(amount),
            "user_id": user_id,
        }

        return await self.manager.create_idempotency_record(
            idempotency_key,
            user_id,
            "send_transaction",
            request_data,
            ttl_hours=1,
        )

    async def link_transaction_to_idempotency(
        self, record: IdempotencyRecord, transaction: Transaction
    ) -> None:
        """Link completed transaction to idempotency record."""
        # Also set idempotency key on transaction
        transaction.idempotency_key = record.idempotency_key

        response_data = {
            "transaction_id": transaction.id,
            "tx_hash": transaction.tx_hash,
            "status": transaction.status,
        }

        await self.manager.update_idempotency_record(
            record, "success", response_data, int(transaction.id) if transaction.id else None
        )


def get_idempotency_manager() -> IdempotencyManager:
    """Get idempotency manager with database session."""
    db = next(get_db())
    return IdempotencyManager(db)


def get_transaction_idempotency() -> TransactionIdempotency:
    """Get transaction idempotency manager with database session."""
    db = next(get_db())
    return TransactionIdempotency(db)
