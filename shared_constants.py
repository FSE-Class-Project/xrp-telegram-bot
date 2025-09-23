"""Shared constants for XRP operations across backend and bot modules."""

from __future__ import annotations

from decimal import Decimal

# XRP Network Constants (TestNet values)
ACCOUNT_RESERVE = Decimal("1")  # Base reserve for account
OWNER_RESERVE = Decimal("0.2")  # Reserve per owned object
MIN_ACCOUNT_BALANCE = Decimal("1")  # Minimum for activation
STANDARD_FEE = Decimal("0.00001")  # Typical network fee
DUST_THRESHOLD = Decimal("0.001")  # Minimum practical amount

# Transaction limits
MAX_XRP_SUPPLY = Decimal("100000000000")  # 100 billion XRP
PRACTICAL_MAX_TRANSACTION = Decimal("1000000")  # 1 million XRP per transaction

# Faucet settings
FAUCET_AMOUNT = 10  # TestNet XRP amount from faucet
