"""Services module initialization."""
from __future__ import annotations

# Import services for easy access
from .xrp_service import xrp_service
from .user_service import user_service

# Import TypedDict type definitions from types.py
from .types import (
    # Transaction types
    TransactionResultDict,
    XRPBalanceDict,
    TransactionHistoryItemDict,
    TransactionHistoryDict,
    PriceDataDict,
    WalletCreationResultDict,
    # User types
    UserCreationDataDict,
    UserDataDict,
    # API types
    BalanceResponseDict,
    SendTransactionRequestDict,
    TransactionResponseDict,
    # XRP Ledger types
    XRPAccountInfoDict,
    XRPTransactionMetadataDict,
    FaucetResponseDict,
    # Settings types
    UserSettingsDict,
    # Error and validation types
    ServiceErrorDict,
    AddressValidationDict,
    # Cache types
    CacheEntryDict,
    # Utility functions
    decimal_to_float,
    float_to_decimal,
    drops_to_xrp,
    xrp_to_drops,
)

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