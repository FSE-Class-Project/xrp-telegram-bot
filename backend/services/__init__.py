"""Services module initialization."""

from __future__ import annotations

# Import TypedDict type definitions from types.py
from .types import (
    AddressValidationDict,
    # API types
    BalanceResponseDict,
    # Cache types
    CacheEntryDict,
    FaucetResponseDict,
    PriceDataDict,
    SendTransactionRequestDict,
    # Error and validation types
    ServiceErrorDict,
    TransactionHistoryDict,
    TransactionHistoryItemDict,
    TransactionResponseDict,
    # Transaction types
    TransactionResultDict,
    # User types
    UserCreationDataDict,
    UserDataDict,
    # Settings types
    UserSettingsDict,
    WalletCreationResultDict,
    # XRP Ledger types
    XRPAccountInfoDict,
    XRPBalanceDict,
    XRPTransactionMetadataDict,
    # Utility functions
    decimal_to_float,
    drops_to_xrp,
    float_to_decimal,
    xrp_to_drops,
)
from .user_service import user_service

# Import services for easy access
from .xrp_service import xrp_service

__all__ = [
    # Services
    "xrp_service",
    "user_service",
    # TypedDict types from types.py
    "TransactionResultDict",
    "XRPBalanceDict",
    "TransactionHistoryItemDict",
    "TransactionHistoryDict",
    "PriceDataDict",
    "WalletCreationResultDict",
    "UserCreationDataDict",
    "UserDataDict",
    "BalanceResponseDict",
    "SendTransactionRequestDict",
    "TransactionResponseDict",
    "XRPAccountInfoDict",
    "XRPTransactionMetadataDict",
    "FaucetResponseDict",
    "UserSettingsDict",
    "ServiceErrorDict",
    "AddressValidationDict",
    "CacheEntryDict",
    # Utility functions
    "decimal_to_float",
    "float_to_decimal",
    "drops_to_xrp",
    "xrp_to_drops",
]
