"""API routes with modern Python typing and Pydantic v2."""
from __future__ import annotations
from typing import Annotated, TypeAlias
from datetime import datetime, timezone
from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
import httpx

from ..database.connection import get_db
from ..services.user_service import user_service
from ..services.xrp_service import xrp_service
from ..database.models import User

# Type aliases
TelegramID: TypeAlias = str
XRPAddress: TypeAlias = str

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["API"])


# Pydantic v2 models with modern typing
class UserRegistration(BaseModel):
    """User registration request model."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    telegram_id: TelegramID
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    telegram_last_name: str | None = None
    
    @field_validator('telegram_id')
    @classmethod
    def validate_telegram_id(cls, v: str) -> str:
        """Validate Telegram ID format."""
        if not v or not v.isdigit():
            raise ValueError('Invalid Telegram ID format')
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
    
    @field_validator('to_address')
    @classmethod
    def validate_xrp_address(cls, v: str) -> str:
        """Validate XRP address format."""
        if not xrp_service.validate_address(v):
            raise ValueError('Invalid XRP address format')
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount is positive and has correct precision."""
        # Check if amount is positive
        if v <= 0:
            raise ValueError('Amount must be positive')
        
        # XRP has 6 decimal places max
        # Use string representation to check decimal places
        str_value = str(v)
        if '.' in str_value:
            decimal_places = len(str_value.split('.')[1])
            if decimal_places > 6:
                raise ValueError('XRP supports maximum 6 decimal places')
        
        return v


class TransactionResponse(BaseModel):
    """Transaction response model."""
    success: bool
    tx_hash: str | None = None
    error: str | None = None
    amount: Decimal | None = None
    fee: Decimal | None = None
    ledger_index: int | None = None
    
    @model_validator(mode='after')
    def validate_response(self) -> TransactionResponse:
        """Ensure response has either success data or error."""
        if self.success and not self.tx_hash:
            raise ValueError('Successful transaction must have tx_hash')
        if not self.success and not self.error:
            raise ValueError('Failed transaction must have error message')
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


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str
    database: bool
    xrp_ledger: bool


# Dependency for getting current user
async def get_current_user(
    telegram_id: Annotated[str, Path(description="Telegram user ID")],
    db: Session = Depends(get_db)
) -> User:
    """Get current user from database."""
    user = user_service.get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


# Routes with modern typing
@router.post(
    "/user/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User successfully registered"},
        400: {"description": "Invalid registration data"},
        500: {"description": "Internal server error"}
    }
)
async def register_user(
    registration: UserRegistration,
    db: Session = Depends(get_db)
) -> UserResponse:
    """Register a new user and create XRP wallet."""
    try:
        user = await user_service.create_user(
            db=db,
            telegram_id=registration.telegram_id,
            telegram_username=registration.telegram_username,
            telegram_first_name=registration.telegram_first_name,
            telegram_last_name=registration.telegram_last_name
        )
        
        # Ensure wallet exists before accessing
        if not user.wallet:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create wallet for user"
            )
        
        return UserResponse(
            user_id=user.id,
            telegram_id=user.telegram_id,
            xrp_address=user.wallet.xrp_address,
            balance=Decimal(str(user.wallet.balance))
        )
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/wallet/balance/{telegram_id}",
    response_model=BalanceResponse,
    responses={
        200: {"description": "Balance retrieved successfully"},
        404: {"description": "User or wallet not found"}
    }
)
async def get_balance(
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
) -> BalanceResponse:
    """Get user's XRP balance."""
    if not user.wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    # Update balance from blockchain
    balance_info = await user_service.update_balance(db, user)
    
    # Calculate available balance (minus reserve)
    available = max(Decimal(str(balance_info)) - Decimal("10"), Decimal("0"))
    
    return BalanceResponse(
        address=user.wallet.xrp_address,
        balance=Decimal(str(balance_info)),
        available_balance=available,
        last_updated=user.wallet.last_balance_update
    )


@router.post(
    "/transaction/send",
    response_model=TransactionResponse,
    responses={
        200: {"description": "Transaction sent successfully"},
        400: {"description": "Invalid transaction data"},
        404: {"description": "User not found"},
        402: {"description": "Insufficient balance"}
    }
)
async def send_transaction(
    request: SendTransactionRequest,
    db: Session = Depends(get_db)
) -> TransactionResponse:
    """Send XRP to another address."""
    # Get sender
    sender = user_service.get_user_by_telegram_id(db, request.from_telegram_id)
    
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender not found"
        )
    
    # Send transaction
    result = await user_service.send_xrp(
        db=db,
        sender=sender,
        recipient_address=request.to_address,
        amount=float(request.amount),  # Convert Decimal to float for XRP
        memo=request.memo
    )
    
    if not result["success"]:
        # Check for specific error types
        error_msg = result.get("error", "Transaction failed")
        if "Insufficient balance" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    return TransactionResponse(
        success=result["success"],
        tx_hash=result.get("tx_hash"),
        amount=Decimal(str(result.get("amount", 0))),
        fee=Decimal(str(result.get("fee", 0))),
        ledger_index=result.get("ledger_index"),
        error=result.get("error")
    )


@router.get(
    "/transaction/history/{telegram_id}",
    response_model=TransactionHistoryResponse,
    responses={
        200: {"description": "Transaction history retrieved"},
        404: {"description": "User not found"}
    }
)
async def get_transaction_history(
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db)
) -> TransactionHistoryResponse:
    """Get user's transaction history with pagination."""
    history = user_service.get_transaction_history(
        db, user, limit=limit, offset=offset
    )
    
    transactions = [
        TransactionHistoryItem(
            hash=tx["hash"] or "",
            amount=Decimal(str(tx["amount"])),
            fee=Decimal(str(tx["fee"])),
            recipient=tx["recipient"],
            status=tx["status"],
            timestamp=datetime.fromisoformat(tx["timestamp"]),
            error=tx.get("error")
        )
        for tx in history
    ]
    
    return TransactionHistoryResponse(
        transactions=transactions,
        total_count=len(transactions)
    )


@router.get(
    "/price/current",
    response_model=PriceInfo,
    responses={
        200: {"description": "Price retrieved successfully"},
        503: {"description": "Price service unavailable"}
    }
)
async def get_current_price() -> PriceInfo:
    """Get current XRP price from CoinGecko."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "ripple",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true"
                }
            )
            
            if response.status_code == 200:
                data = response.json()["ripple"]
                return PriceInfo(
                    price_usd=Decimal(str(data["usd"])),
                    change_24h=Decimal(str(data.get("usd_24h_change", 0))),
                    market_cap=Decimal(str(data.get("usd_market_cap", 0))),
                    volume_24h=Decimal(str(data.get("usd_24h_vol", 0))),
                    last_updated=datetime.now(timezone.utc)
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Price service unavailable"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Price service timeout"
        )
    except Exception as e:
        logger.error(f"Price fetch error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"}
    }
)
async def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Health check endpoint for monitoring."""
    from ..config import settings
    
    # Check database connection
    db_healthy = False
    try:
        # Use text() to wrap the SQL statement for proper typing
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
    
    # Check XRP Ledger connection
    xrp_healthy = False
    try:
        # Try to get TestNet status
        balance = await xrp_service.get_balance("rN7n7enGRiLVpHJgWoEjPaXb7JkwD8nH5q")
        xrp_healthy = balance is not None
    except Exception as e:
        logger.error(f"XRP Ledger health check failed: {str(e)}")
    
    # Overall health status
    is_healthy = db_healthy and xrp_healthy
    
    response = HealthCheckResponse(
        status="healthy" if is_healthy else "unhealthy",
        service="XRP Telegram Bot API",
        version=settings.APP_VERSION,
        database=db_healthy,
        xrp_ledger=xrp_healthy
    )
    
    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump()
        )
    
    return response