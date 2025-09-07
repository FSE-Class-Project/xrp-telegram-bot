"""Services module initialization."""
from __future__ import annotations

# Import services for easy access
from .xrp_service import xrp_service
from .user_service import user_service

# Import types if needed
from .types import (
    TransactionResult,
    XRPBalance,
    TransactionHistoryItem,
    TransactionHistory,
    PriceData,
    WalletCreationResult,
    UserCreationData,
    UserData,
    BalanceResponse,
    SendTransactionRequest,
    TransactionResponse,
    ServiceError,
    AddressValidation,
)

__all__ = [
    # Services
    "xrp_service",
    "user_service",
    # Types
    "TransactionResult",
    "XRPBalance", 
    "TransactionHistoryItem",
    "TransactionHistory",
    "PriceData",
    "WalletCreationResult",
    "UserCreationData",
    "UserData",
    "BalanceResponse",
    "SendTransactionRequest",
    "TransactionResponse",
    "ServiceError",
    "AddressValidation",
]