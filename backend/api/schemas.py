"""API schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class TransactionStatus(str, Enum):
    """Transaction status enum."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Currency(str, Enum):
    """Supported currencies."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    BTC = "BTC"


class Network(str, Enum):
    """XRP network types."""

    MAINNET = "mainnet"
    TESTNET = "testnet"
    DEVNET = "devnet"


# Base schemas
class BaseResponse(BaseModel):
    """Base response model."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    message: str | None = None


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime | None = None


# User schemas
class UserBase(BaseModel):
    """Base user schema."""

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class UserCreate(UserBase):
    """User creation schema."""

    pass


class UserUpdate(BaseModel):
    """User update schema."""

    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase, TimestampMixin):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    wallets: list[WalletResponse] = []
    settings: UserSettingsResponse | None = None


# Wallet schemas
class WalletBase(BaseModel):
    """Base wallet schema."""

    address: str
    is_testnet: bool = True


class WalletCreate(BaseModel):
    """Wallet creation schema."""

    user_id: int
    is_testnet: bool = True

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("User ID must be positive")
        return v


class WalletUpdate(BaseModel):
    """Wallet update schema."""

    is_active: bool | None = None


class WalletResponse(WalletBase, TimestampMixin):
    """Wallet response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    balance: Decimal = Field(default=Decimal("0"))
    is_active: bool
    sequence: int | None = None


class WalletBalanceResponse(BaseResponse):
    """Wallet balance response."""

    address: str
    balance: Decimal = Field(default=Decimal("0"))
    reserved_balance: Decimal = Field(default=Decimal("1"))
    available_balance: Decimal = Field(default=Decimal("0"))

    @model_validator(mode="after")
    def calculate_available(self) -> WalletBalanceResponse:
        """Calculate available balance."""
        self.available_balance = max(self.balance - self.reserved_balance, Decimal("0"))
        return self


# Transaction schemas
class TransactionBase(BaseModel):
    """Base transaction schema."""

    sender_address: str
    receiver_address: str
    amount: Decimal = Field(gt=0)

    @field_validator("sender_address", "receiver_address")
    @classmethod
    def validate_xrp_address(cls, v: str) -> str:
        """Validate XRP address format."""
        if not v.startswith("r") or len(v) < 25 or len(v) > 35:
            raise ValueError("Invalid XRP address format")
        return v


class TransactionCreate(TransactionBase):
    """Transaction creation schema."""

    user_id: int
    destination_tag: int | None = Field(default=None, ge=0, le=4294967295)
    memo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_addresses(self) -> TransactionCreate:
        """Ensure sender and receiver are different."""
        if self.sender_address == self.receiver_address:
            raise ValueError("Cannot send to the same address")
        return self


class TransactionResponse(TransactionBase, TimestampMixin):
    """Transaction response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_hash: str
    fee: Decimal = Field(default=Decimal("0.00001"))
    status: TransactionStatus
    ledger_index: int | None = None
    sequence: int | None = None
    destination_tag: int | None = None
    memo: str | None = None
    confirmed_at: datetime | None = None


class TransactionHistoryQuery(BaseModel):
    """Transaction history query parameters."""

    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    status: TransactionStatus | None = None
    address: str | None = None

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str | None) -> str | None:
        if v and not v.startswith("r"):
            raise ValueError("Invalid XRP address")
        return v


class TransactionHistoryResponse(BaseResponse):
    """Transaction history response."""

    transactions: list[TransactionResponse]
    total: int
    page: int = 1
    pages: int = 1
    limit: int = 10

    @model_validator(mode="after")
    def calculate_pages(self) -> TransactionHistoryResponse:
        """Calculate total pages."""
        if self.total > 0 and self.limit > 0:
            self.pages = (self.total + self.limit - 1) // self.limit
            self.page = max(1, min(self.page, self.pages))
        return self


# Price schemas
class PriceData(BaseModel):
    """Price data schema."""

    price: Decimal
    currency: Currency
    change_24h: Decimal | None = Field(default=None)
    change_percentage_24h: Decimal | None = Field(default=None)
    volume_24h: Decimal | None = Field(default=None)
    market_cap: Decimal | None = Field(default=None)
    last_updated: datetime


class PriceResponse(BaseResponse):
    """Price response schema."""

    data: dict[str, PriceData]
    source: str = "CoinGecko"


# User settings schemas
class UserSettingsBase(BaseModel):
    """Base user settings schema."""

    language: str = Field(default="en", pattern="^[a-z]{2}$")
    currency: Currency = Currency.USD
    notifications_enabled: bool = True
    price_alerts_enabled: bool = False
    transaction_confirmations: bool = True
    show_testnet_warning: bool = True


class UserSettingsCreate(UserSettingsBase):
    """User settings creation schema."""

    user_id: int


class UserSettingsUpdate(BaseModel):
    """User settings update schema."""

    language: str | None = Field(default=None, pattern="^[a-z]{2}$")
    currency: Currency | None = None
    notifications_enabled: bool | None = None
    price_alerts_enabled: bool | None = None
    price_alert_threshold: Decimal | None = Field(default=None, gt=0)
    transaction_confirmations: bool | None = None
    show_testnet_warning: bool | None = None


class UserSettingsResponse(UserSettingsBase, TimestampMixin):
    """User settings response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    price_alert_threshold: Decimal | None = Field(default=None)


# Authentication schemas
class TokenData(BaseModel):
    """JWT token data."""

    telegram_id: int
    exp: datetime
    iat: datetime
    jti: str | None = None


class TokenResponse(BaseResponse):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Expiration time in seconds")


# Health check schemas
class HealthStatus(BaseModel):
    """Service health status."""

    service: str
    status: str
    latency_ms: float | None = None
    details: dict[str, Any] | None = None


class HealthResponse(BaseResponse):
    """Health check response."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    environment: str
    version: str
    services: list[HealthStatus]

    @model_validator(mode="after")
    def check_overall_health(self) -> HealthResponse:
        """Determine overall health status."""
        if any(s.status != "healthy" for s in self.services):
            self.success = False
            self.message = "Some services are unhealthy"
        return self


# Webhook schemas for Telegram updates
class TelegramUpdate(BaseModel):
    """Telegram update schema."""

    update_id: int
    message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None
    inline_query: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_update_type(self) -> TelegramUpdate:
        """Ensure at least one update type is present."""
        if not any([self.message, self.callback_query, self.inline_query]):
            raise ValueError("Invalid update: no content")
        return self


# Transaction request schemas
class SendTransactionRequest(BaseModel):
    """Send transaction request model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    from_telegram_id: str
    to_address: str
    amount: Decimal = Field(gt=0)
    memo: str | None = Field(None, max_length=512)

    @field_validator("to_address")
    @classmethod
    def validate_xrp_address(cls, v: str) -> str:
        """Validate XRP address format."""
        import re

        if not v.startswith("r"):
            raise ValueError("XRP address must start with 'r'")

        if len(v) < 25 or len(v) > 34:
            raise ValueError("XRP address must be 25-34 characters long")

        pattern = r"^r[a-zA-Z0-9]{24,33}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid XRP address format")

        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate XRP amount."""
        if v <= 0:
            raise ValueError("Amount must be positive")

        # Check minimum transaction amount (1 drop = 0.000001 XRP)
        min_amount = Decimal("0.000001")
        if v < min_amount:
            raise ValueError(f"Amount must be at least {min_amount} XRP")

        # Check maximum practical amount
        max_amount = Decimal("100000000000")  # 100 billion XRP
        if v > max_amount:
            raise ValueError(f"Amount cannot exceed {max_amount} XRP")

        return v


# Error schemas
class ErrorDetail(BaseModel):
    """Error detail schema."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    success: bool = False
    message: str
    errors: list[ErrorDetail] | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
