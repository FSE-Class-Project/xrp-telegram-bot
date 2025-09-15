"""Type definitions for services module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, NotRequired, TypedDict


# Transaction type definitions
class TransactionResultDict(TypedDict):
    """Result of a transaction operation."""

    success: bool
    tx_hash: NotRequired[str]
    ledger_index: NotRequired[int]
    fee: NotRequired[Decimal]  # Use Decimal for financial precision
    amount: NotRequired[Decimal]  # Use Decimal for financial precision
    error: NotRequired[str]
    timestamp: NotRequired[datetime]


class XRPBalanceDict(TypedDict):
    """XRP balance information."""

    address: str
    balance: Decimal  # Use Decimal for financial precision
    last_updated: datetime | None
    is_activated: bool


class TransactionHistoryItemDict(TypedDict):
    """Single transaction in history."""

    hash: str | None
    type: Literal["payment", "trust_set", "offer_create", "offer_cancel", "other"]
    amount: Decimal  # Use Decimal for financial precision
    fee: Decimal  # Use Decimal for financial precision
    sender: str
    recipient: str
    timestamp: datetime | None
    status: Literal["pending", "confirmed", "failed"]
    ledger_index: int | None
    memo: NotRequired[str]
    error_message: NotRequired[str]


class TransactionHistoryDict(TypedDict):
    """Transaction history response."""

    transactions: list[TransactionHistoryItemDict]
    total_count: int
    has_more: bool


class PriceDataDict(TypedDict):
    """Cryptocurrency price data."""

    symbol: str
    price_usd: Decimal  # Use Decimal for financial precision
    price_btc: NotRequired[Decimal]
    change_24h: NotRequired[Decimal]
    change_percentage_24h: NotRequired[float]  # Percentage can stay as float
    market_cap: NotRequired[Decimal]
    volume_24h: NotRequired[Decimal]
    high_24h: NotRequired[Decimal]
    low_24h: NotRequired[Decimal]
    last_updated: datetime


class WalletCreationResultDict(TypedDict):
    """Result of wallet creation."""

    address: str
    encrypted_secret: str
    balance: Decimal  # Use Decimal for financial precision
    funded: bool
    funding_amount: NotRequired[Decimal]
    error: NotRequired[str]


# User service type definitions
class UserCreationDataDict(TypedDict):
    """Data for creating a new user."""

    telegram_id: str
    telegram_username: NotRequired[str]
    telegram_first_name: NotRequired[str]
    telegram_last_name: NotRequired[str]


class UserDataDict(TypedDict):
    """Complete user data."""

    id: int
    telegram_id: str
    telegram_username: str | None
    telegram_first_name: str | None
    telegram_last_name: str | None
    xrp_address: str
    balance: Decimal  # Use Decimal for financial precision
    is_active: bool
    created_at: datetime
    updated_at: datetime


# API Response type definitions
class BalanceResponseDict(TypedDict):
    """Balance API response."""

    address: str
    balance: float  # API responses can use float for JSON compatibility
    last_updated: str | None


class SendTransactionRequestDict(TypedDict):
    """Send transaction request."""

    from_telegram_id: str
    to_address: str
    amount: float  # API requests can accept float
    memo: NotRequired[str]


class TransactionResponseDict(TypedDict):
    """Transaction API response."""

    success: bool
    tx_hash: NotRequired[str]
    error: NotRequired[str]
    amount: NotRequired[float]  # API responses can use float
    fee: NotRequired[float]  # API responses can use float


# XRP Ledger specific type definitions
class XRPAccountInfoDict(TypedDict):
    """XRP Ledger account information."""

    account: str
    balance: str  # In drops (string from XRP Ledger)
    flags: int
    ledger_current_index: int
    owner_count: int
    previous_txn_id: str
    previous_txn_lgr_seq: int
    sequence: int


class XRPTransactionMetadataDict(TypedDict):
    """XRP transaction metadata."""

    transaction_index: int
    transaction_result: str
    delivered_amount: NotRequired[str]  # In drops


class FaucetResponseDict(TypedDict):
    """TestNet faucet response."""

    account: str
    amount: int  # In drops
    balance: int  # In drops
    hash: str
    code: NotRequired[str]
    message: NotRequired[str]


# Settings type definitions
class UserSettingsDict(TypedDict):
    """User preference settings."""

    user_id: int
    price_alerts: bool
    transaction_notifications: bool
    currency_display: Literal["USD", "EUR", "GBP", "ZAR", "JPY", "BTC", "ETH"]
    language: Literal["en", "es", "fr", "de", "pt", "zh"]
    two_factor_enabled: bool


# Error type definitions
class ServiceErrorDict(TypedDict):
    """Service error details."""

    code: str
    message: str
    details: NotRequired[dict[str, Any]]
    timestamp: datetime


# Validation type definitions
class AddressValidationDict(TypedDict):
    """Address validation result."""

    is_valid: bool
    address: str
    network: Literal["mainnet", "testnet", "devnet"]
    is_activated: NotRequired[bool]
    error: NotRequired[str]


# Cache type definitions
class CacheEntryDict(TypedDict):
    """Cache entry for Redis or in-memory caching."""

    key: str
    value: Any
    ttl: int
    created_at: datetime
    expires_at: datetime


# Utility functions for converting between Decimal and float
def decimal_to_float(value: Decimal) -> float:
    """Convert Decimal to float for JSON serialization."""
    return float(value)


def float_to_decimal(value: float | str) -> Decimal:
    """Convert float or string to Decimal for precise calculations."""
    return Decimal(str(value))


# XRP specific conversion utilities
def drops_to_xrp(drops: str | int) -> Decimal:
    """Convert drops (smallest XRP unit) to XRP."""
    return Decimal(str(drops)) / Decimal("1000000")


def xrp_to_drops(xrp: Decimal | float) -> str:
    """Convert XRP to drops (smallest XRP unit)."""
    if isinstance(xrp, float):
        xrp = Decimal(str(xrp))
    return str(int(xrp * Decimal("1000000")))
