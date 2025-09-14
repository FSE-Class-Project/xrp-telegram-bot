"""API routes"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, TypeAlias, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.auth import verify_api_key
from backend.api.middleware import get_idempotency_key, limiter, rate_limit_transactions
from backend.config import settings
from backend.database.connection import get_db
from backend.database.models import User
from backend.services import user_service, xrp_service

# Type aliases
TelegramID: TypeAlias = str
XRPAddress: TypeAlias = str


# XRP Network Constants
class XRPConstants:
    """XRP Ledger network constants for validation."""

    # Amount limits
    MIN_DROP = Decimal("0.000001")  # 1 drop (smallest XRP unit)
    MAX_XRP_SUPPLY = Decimal("100000000000")  # 100 billion XRP
    PRACTICAL_MAX_TRANSACTION = Decimal("1000000")  # 1 million XRP per transaction
    DUST_THRESHOLD = Decimal("0.001")  # Minimum practical amount

    # Network requirements
    ACCOUNT_RESERVE = Decimal("10")  # Base reserve for account
    OWNER_RESERVE = Decimal("2")  # Reserve per owned object
    MIN_ACCOUNT_BALANCE = Decimal("20")  # Minimum for activation
    STANDARD_FEE = Decimal("0.00001")  # Typical network fee

    # Business logic limits
    LARGE_TRANSACTION_THRESHOLD = Decimal("10000")  # Flag for large amounts
    MAX_DECIMAL_PLACES = 6


logger = logging.getLogger(__name__)


def validate_transaction_feasibility(
    current_balance: Decimal,
    transaction_amount: Decimal,
    recipient_address: str,
    sender_address: str,
) -> tuple[bool, str]:
    """
    Validate if a transaction is feasible given current constraints.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    # Check account activation
    if current_balance < XRPConstants.MIN_ACCOUNT_BALANCE:
        return (
            False,
            f"Account not activated. Minimum balance required: {XRPConstants.MIN_ACCOUNT_BALANCE} XRP",
        )

    # Calculate total cost including fee
    total_cost = transaction_amount + XRPConstants.STANDARD_FEE

    # Check available balance (minus reserve)
    available_balance = current_balance - XRPConstants.ACCOUNT_RESERVE
    if available_balance < total_cost:
        return (
            False,
            f"Insufficient balance. Available: {available_balance} XRP, Required: {total_cost} XRP (including fee)",
        )

    # Check reserve requirement after transaction
    remaining_balance = current_balance - total_cost
    if remaining_balance < XRPConstants.ACCOUNT_RESERVE:
        return (
            False,
            f"Transaction would violate account reserve requirement. Minimum {XRPConstants.ACCOUNT_RESERVE} XRP must remain",
        )

    # Prevent self-transactions
    if sender_address == recipient_address:
        return False, "Cannot send XRP to your own address"

    return True, ""


# Create router
router = APIRouter(prefix="/api/v1", tags=["API"])


# Shared validation function
def validate_xrp_amount(v: Decimal) -> Decimal:
    """Comprehensive XRP amount validation using network constants."""
    # Convert to Decimal if needed and normalize
    if not isinstance(v, Decimal):
        v = Decimal(str(v))  # type: ignore[unreachable]

    # Basic validation
    if v <= 0:
        raise ValueError("Amount must be positive")

    # Check minimum transaction amount (1 drop)
    if v < XRPConstants.MIN_DROP:
        raise ValueError(f"Amount must be at least {XRPConstants.MIN_DROP} XRP (1 drop)")

    # Check maximum possible amount (sanity check)
    if v > XRPConstants.MAX_XRP_SUPPLY:
        raise ValueError(f"Amount cannot exceed {XRPConstants.MAX_XRP_SUPPLY} XRP")

    # Check decimal precision (XRP supports 6 decimal places max)
    try:
        quantized = v.quantize(Decimal("0.000001"))
        if quantized != v:
            raise ValueError(
                f"XRP supports maximum {XRPConstants.MAX_DECIMAL_PLACES} decimal places"
            )
    except Exception as e:
        raise ValueError("Invalid decimal precision for XRP amount") from e

    # Practical maximum for single transaction (anti-whale protection)
    if v > XRPConstants.PRACTICAL_MAX_TRANSACTION:
        raise ValueError(
            f"Single transaction amount cannot exceed {XRPConstants.PRACTICAL_MAX_TRANSACTION} XRP"
        )

    # Check for dust amounts (very small transactions that waste network resources)
    if v < XRPConstants.DUST_THRESHOLD:
        raise ValueError(
            f"Amount too small: minimum practical amount is {XRPConstants.DUST_THRESHOLD} XRP"
        )

    return v


# Pydantic v2 models
class UserRegistration(BaseModel):
    """User registration request model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    telegram_id: TelegramID
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    telegram_last_name: str | None = None

    @field_validator("telegram_id")
    @classmethod
    def validate_telegram_id(cls, v: str) -> str:
        """Validate Telegram ID format."""
        if not v or not v.isdigit():
            raise ValueError("Invalid Telegram ID format")
        return v


class UserResponse(BaseModel):
    """User response model."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    telegram_id: TelegramID
    xrp_address: XRPAddress
    balance: Decimal


class SendTransactionRequest(BaseModel):
    """Send transaction request model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    from_telegram_id: TelegramID
    to_address: XRPAddress
    amount: Decimal
    memo: str | None = Field(None, max_length=512)

    @field_validator("to_address")
    @classmethod
    def validate_xrp_address(cls, v: str) -> str:
        """Validate XRP address format."""
        if not xrp_service.validate_address(v):
            raise ValueError("Invalid XRP address format")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Comprehensive XRP amount validation using network constants."""
        return validate_xrp_amount(v)


class TransactionResponse(BaseModel):
    """Transaction response model."""

    success: bool
    tx_hash: str | None = None
    error: str | None = None
    amount: Decimal | None = None
    fee: Decimal | None = None
    ledger_index: int | None = None

    @model_validator(mode="after")
    def validate_response(self) -> "TransactionResponse":
        """Ensure response has either success data or error."""
        if self.success and not self.tx_hash:
            raise ValueError("Successful transaction must have tx_hash")
        if not self.success and not self.error:
            raise ValueError("Failed transaction must have error message")
        return self


class BalanceResponse(BaseModel):
    """Balance response model."""

    address: XRPAddress
    balance: Decimal
    available_balance: Decimal
    last_updated: datetime | None = None


class PriceInfo(BaseModel):
    """Price information model."""

    price_usd: Decimal
    change_24h: Decimal | None = None
    market_cap: Decimal | None = None
    volume_24h: Decimal | None = None
    last_updated: datetime


class TransactionHistoryItem(BaseModel):
    """Transaction history item model."""

    hash: str
    amount: Decimal
    fee: Decimal
    recipient: XRPAddress
    status: str
    timestamp: datetime
    error: str | None = None


class TransactionHistoryResponse(BaseModel):
    """Transaction history response model."""

    transactions: list[TransactionHistoryItem]
    total_count: int


class TransactionValidationRequest(BaseModel):
    """Transaction validation request model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    from_telegram_id: TelegramID
    to_address: XRPAddress
    amount: Decimal

    @field_validator("to_address")
    @classmethod
    def validate_xrp_address(cls, v: str) -> str:
        """Validate XRP address format."""
        if not xrp_service.validate_address(v):
            raise ValueError("Invalid XRP address format")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Use the same validation as SendTransactionRequest."""
        return validate_xrp_amount(v)


class TransactionValidationResponse(BaseModel):
    """Transaction validation response model."""

    is_valid: bool
    error_message: str | None = None
    current_balance: Decimal
    available_balance: Decimal
    transaction_cost: Decimal
    estimated_fee: Decimal
    remaining_balance: Decimal | None = None
    warnings: list[str] = []


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str
    database: bool
    xrp_ledger: bool
    redis_cache: bool = False


# Dependency for getting current user
async def get_current_user(
    telegram_id: Annotated[str, Path(description="Telegram user ID")], db: Session = Depends(get_db)
) -> User:
    """Get current user from database."""
    user = user_service.get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# Routes
@router.post(
    "/user/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
    responses={
        201: {"description": "User successfully registered"},
        400: {"description": "Invalid registration data"},
        401: {"description": "Invalid API key"},
        500: {"description": "Internal server error"},
    },
)
# Temporarily disable rate limiting for development debugging
# @limiter.limit("100/hour" if settings.ENVIRONMENT == "development" else "5/hour")
async def register_user(
    request: Request,
    response: Response,
    registration: UserRegistration,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user and create XRP wallet."""
    try:
        user = await user_service.create_user(
            db=db,
            telegram_id=registration.telegram_id,
            telegram_username=registration.telegram_username,
            telegram_first_name=registration.telegram_first_name,
            telegram_last_name=registration.telegram_last_name,
        )

        # Ensure wallet exists before accessing
        if not user.wallet:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create wallet for user",
            )

        # Fix type inference issues by explicitly casting or using intermediate variables
        user_id_value: int = cast(int, user.id)
        telegram_id_value: str = cast(str, user.telegram_id)
        xrp_address_value: str = cast(str, user.wallet.xrp_address)
        balance_value: float = cast(float, user.wallet.balance)

        return UserResponse(
            user_id=user_id_value,
            telegram_id=telegram_id_value,
            xrp_address=xrp_address_value,
            balance=Decimal(str(balance_value)),
        )

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get(
    "/wallet/balance/{telegram_id}",
    response_model=BalanceResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Balance retrieved successfully"},
        401: {"description": "Invalid API key"},
        404: {"description": "User or wallet not found"},
    },
)
async def get_balance(
    user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)
) -> BalanceResponse:
    """Get user's XRP balance."""
    if not user.wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    # Update balance from blockchain
    balance_info = await user_service.update_balance(db, user)

    # Calculate available balance (minus network reserve)
    total_balance = Decimal(str(balance_info))
    available = max(total_balance - XRPConstants.ACCOUNT_RESERVE, Decimal("0"))

    # Type casting for clarity
    xrp_address_value: str = cast(str, user.wallet.xrp_address)

    return BalanceResponse(
        address=xrp_address_value,
        balance=total_balance,
        available_balance=available,
        last_updated=user.wallet.last_balance_update,
    )


@router.post(
    "/transaction/validate",
    response_model=TransactionValidationResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Transaction validation completed"},
        400: {"description": "Invalid validation request"},
        401: {"description": "Invalid API key"},
        404: {"description": "User not found"},
    },
)
async def validate_transaction(
    validation_request: TransactionValidationRequest, db: Session = Depends(get_db)
) -> TransactionValidationResponse:
    """Validate a transaction before sending to provide detailed feedback."""
    # Get sender
    sender = user_service.get_user_by_telegram_id(db, validation_request.from_telegram_id)

    if not sender or not sender.wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sender or wallet not found"
        )

    # Get current balance
    current_balance = await user_service.update_balance(db, sender)
    current_balance_decimal = Decimal(str(current_balance))

    # Calculate costs and balances
    estimated_fee = XRPConstants.STANDARD_FEE
    transaction_cost = validation_request.amount + estimated_fee
    available_balance = max(current_balance_decimal - XRPConstants.ACCOUNT_RESERVE, Decimal("0"))

    # Perform validation
    is_valid, error_message = validate_transaction_feasibility(
        current_balance=current_balance_decimal,
        transaction_amount=validation_request.amount,
        recipient_address=validation_request.to_address,
        sender_address=sender.wallet.xrp_address,
    )

    # Calculate remaining balance if transaction would succeed
    remaining_balance = None
    if is_valid:
        remaining_balance = current_balance_decimal - transaction_cost

    # Generate warnings
    warnings = []
    if validation_request.amount > XRPConstants.LARGE_TRANSACTION_THRESHOLD:
        warnings.append(f"Large transaction amount: {validation_request.amount} XRP")

    if is_valid and remaining_balance:
        if remaining_balance < XRPConstants.ACCOUNT_RESERVE + Decimal("1"):
            warnings.append("Transaction will leave account with minimal reserve")

    if validation_request.amount < XRPConstants.DUST_THRESHOLD * 10:  # 10x dust threshold
        warnings.append("Small transaction amount may have high relative fees")

    return TransactionValidationResponse(
        is_valid=is_valid,
        error_message=error_message if not is_valid else None,
        current_balance=current_balance_decimal,
        available_balance=available_balance,
        transaction_cost=transaction_cost,
        estimated_fee=estimated_fee,
        remaining_balance=remaining_balance,
        warnings=warnings,
    )


@router.post(
    "/transaction/send",
    response_model=TransactionResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Transaction sent successfully"},
        400: {"description": "Invalid transaction data"},
        401: {"description": "Invalid API key"},
        404: {"description": "User not found"},
        402: {"description": "Insufficient balance"},
    },
)
@limiter.limit(rate_limit_transactions)
async def send_transaction(
    request: Request,
    response: Response,
    transaction: SendTransactionRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> TransactionResponse:
    """Send XRP to another address with comprehensive validation and idempotency."""
    from ..utils.idempotency import IdempotencyKey, TransactionIdempotency

    # Get sender
    sender = user_service.get_user_by_telegram_id(db, transaction.from_telegram_id)

    if not sender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender not found")

    # Check if sender has a wallet
    if not sender.wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender wallet not found")

    # Get current balance and perform enhanced validation
    current_balance = await user_service.update_balance(db, sender)
    current_balance_decimal = Decimal(str(current_balance))

    # Validate transaction feasibility
    is_valid, error_message = validate_transaction_feasibility(
        current_balance=current_balance_decimal,
        transaction_amount=transaction.amount,
        recipient_address=transaction.to_address,
        sender_address=sender.wallet.xrp_address,
    )

    if not is_valid:
        # Determine appropriate HTTP status code based on error type
        if "balance" in error_message.lower() or "reserve" in error_message.lower():
            status_code = status.HTTP_402_PAYMENT_REQUIRED
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(status_code=status_code, detail=error_message)

    # Log large transaction attempts for monitoring
    if transaction.amount > XRPConstants.LARGE_TRANSACTION_THRESHOLD:
        logger.warning(
            f"Large transaction attempted: {transaction.amount} XRP by user {sender.telegram_id}"
        )

    # Handle idempotency for transaction safety
    tx_idempotency = TransactionIdempotency(db)

    # Generate idempotency key if not provided
    if not idempotency_key:
        assert sender.id is not None, "Sender ID cannot be None"
        idempotency_key = IdempotencyKey.from_request(
            user_id=int(sender.id),  # type: ignore[arg-type]
            operation="send_transaction",
            data={
                "to_address": transaction.to_address,
                "amount": str(transaction.amount),
                "memo": transaction.memo or "",
            },
        )

    # Check for duplicate transaction
    assert sender.id is not None, "Sender ID cannot be None"
    existing = await tx_idempotency.check_transaction_idempotency(
        idempotency_key=idempotency_key,
        user_id=int(sender.id),  # type: ignore[arg-type]
        to_address=transaction.to_address,
        amount=float(transaction.amount),
    )

    if existing:
        # Return existing transaction result
        if hasattr(existing, "tx_hash"):  # It's a Transaction
            return TransactionResponse(
                success=existing.status == "success",  # type: ignore[arg-type]
                tx_hash=str(existing.tx_hash) if existing.tx_hash else None,  # type: ignore[arg-type]
                amount=Decimal(str(existing.amount)),
                fee=Decimal(str(existing.fee)),
            )
        else:  # It's an IdempotencyRecord
            if existing.response_status == "processing":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Transaction is already being processed",
                )
            elif existing.response_status == "success" and existing.response_data:
                import json

                response_data = json.loads(str(existing.response_data))  # type: ignore[arg-type]
                return TransactionResponse(
                    success=True,
                    tx_hash=response_data.get("tx_hash"),
                    amount=Decimal(str(response_data.get("amount", 0))),
                    fee=Decimal(str(response_data.get("fee", 0))),
                )

    # Create idempotency record for new transaction
    assert sender.id is not None, "Sender ID cannot be None"
    idempotency_record = await tx_idempotency.create_transaction_idempotency(
        idempotency_key=idempotency_key,
        user_id=int(sender.id),  # type: ignore[arg-type]
        to_address=transaction.to_address,
        amount=float(transaction.amount),
    )

    try:
        # Send transaction
        result = await user_service.send_xrp(
            db=db,
            sender=sender,
            recipient_address=transaction.to_address,
            amount=float(transaction.amount),  # Convert Decimal to float for XRP
            memo=transaction.memo,
        )
    except Exception as e:
        # Update idempotency record with error
        await tx_idempotency.manager.update_idempotency_record(
            idempotency_record, "error", {"error": str(e)}
        )
        raise

    if not result["success"]:
        # Check for specific error types
        error_msg = result.get("error", "Transaction failed")
        if "Insufficient balance" in error_msg:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Update idempotency record with success
    if result["success"] and "transaction_id" in result:
        from ..database.models import Transaction

        tx_record = db.query(Transaction).filter(Transaction.id == result["transaction_id"]).first()
        if tx_record:
            await tx_idempotency.link_transaction_to_idempotency(idempotency_record, tx_record)

    return TransactionResponse(
        success=result["success"],
        tx_hash=result.get("tx_hash"),
        amount=Decimal(str(result.get("amount", 0))),
        fee=Decimal(str(result.get("fee", 0))),
    )


@router.get(
    "/transaction/history/{telegram_id}",
    response_model=TransactionHistoryResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Transaction history retrieved"},
        401: {"description": "Invalid API key"},
        404: {"description": "User not found"},
    },
)
async def get_transaction_history(
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> TransactionHistoryResponse:
    """Get user's transaction history with pagination."""
    history = user_service.get_transaction_history(db, user, limit=limit, offset=offset)

    transactions = [
        TransactionHistoryItem(
            hash=tx["hash"] or "",
            amount=Decimal(str(tx["amount"])),
            fee=Decimal(str(tx["fee"])),
            recipient=tx["recipient"],
            status=tx["status"],
            timestamp=datetime.fromisoformat(tx["timestamp"]),
            error=tx.get("error"),
        )
        for tx in history
    ]

    return TransactionHistoryResponse(transactions=transactions, total_count=len(transactions))


@router.get(
    "/price/current",
    response_model=PriceInfo,
    responses={
        200: {"description": "Price retrieved successfully"},
        503: {"description": "Price service unavailable"},
    },
)
@limiter.limit("30/minute")  # Allow reasonable price checking
async def get_current_price(request: Request, response: Response) -> PriceInfo:
    """Get current XRP price from CoinGecko."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            api_response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "ripple",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                },
            )

            if api_response.status_code == 200:
                data = api_response.json()["ripple"]
                return PriceInfo(
                    price_usd=Decimal(str(data["usd"])),
                    change_24h=Decimal(str(data.get("usd_24h_change", 0))),
                    market_cap=Decimal(str(data.get("usd_market_cap", 0))),
                    volume_24h=Decimal(str(data.get("usd_24h_vol", 0))),
                    last_updated=datetime.now(timezone.utc),
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Price service unavailable",
                )

    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Price service timeout"
        ) from e
    except Exception as e:
        logger.error(f"Price fetch error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"},
    },
)
async def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Health check endpoint for monitoring."""
    from ..services.cache_service import get_cache_service

    # Check database connection
    db_healthy = False
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")

    # Check XRP Ledger connection
    xrp_healthy = False
    try:
        # Try to get TestNet status using a known TestNet faucet address
        balance = await xrp_service.get_balance("rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe")
        xrp_healthy = balance is not None
    except Exception as e:
        logger.error(f"XRP Ledger health check failed: {str(e)}")

    # Check Redis cache
    redis_healthy = False
    try:
        cache = get_cache_service()
        cache_status = cache.health_check()
        redis_healthy = cache_status.get("connected", False)
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")

    # Overall health status - service can run without Redis
    is_healthy = db_healthy and xrp_healthy
    service_status = "healthy" if is_healthy else "degraded" if not redis_healthy else "unhealthy"

    response = HealthCheckResponse(
        status=service_status,
        service="XRP Telegram Bot API",
        version=settings.APP_VERSION,
        database=db_healthy,
        xrp_ledger=xrp_healthy,
        redis_cache=redis_healthy,
    )

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response.model_dump()
        )

    return response
