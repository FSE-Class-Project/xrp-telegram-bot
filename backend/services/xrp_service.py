"""XRP Ledger integration service."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import autofill, sign, submit_and_wait
from xrpl.models.requests import AccountInfo, AccountTx
from xrpl.models.transactions import Memo, Payment
from xrpl.utils import drops_to_xrp, xrp_to_drops
from xrpl.wallet import Wallet as XRPLWallet  # Alias to avoid conflict with DB model

from ..config import settings
from ..constants import ACCOUNT_RESERVE, STANDARD_FEE
from ..utils.encryption import encryption_service

logger = logging.getLogger(__name__)


class XRPService:
    """Service for interacting with XRP Ledger."""

    def __init__(self):
        """Initialize XRP client connections."""
        try:
            self.json_rpc_url = settings.XRP_JSON_RPC_URL
            self.websocket_url = settings.XRP_WEBSOCKET_URL
            self.network = settings.XRP_NETWORK
            self.client = AsyncJsonRpcClient(self.json_rpc_url)
            logger.info(f"Initialized XRP service for network: {self.network}")
        except Exception as e:
            logger.error(f"Failed to initialize XRP service: {e}")
            raise

    def create_wallet(self) -> tuple[str, str]:
        """Create a new XRP wallet.

        Returns: (address, encrypted_secret).
        """
        try:
            # Use Wallet.create() instead of generate() for xrpl-py 2.5.0
            wallet = XRPLWallet.create()
            logger.debug("Created new XRP wallet")

            # Ensure seed exists before encrypting
            if not wallet.seed:
                logger.error("Wallet seed is None - cannot create wallet")
                raise ValueError("Wallet seed is None - cannot create wallet")

            # Encrypt the secret key (use seed instead of secret)
            encrypted_secret = encryption_service.encrypt(wallet.seed)
            logger.info(f"Successfully created wallet: {wallet.classic_address}")

            return wallet.classic_address, encrypted_secret
        except Exception as e:
            logger.error(f"Failed to create wallet: {e}")
            raise

    async def fund_wallet_from_faucet(self, address: str) -> bool:
        """Fund a TestNet wallet using the XRP faucet.

        Note: The faucet always provides 10 XRP regardless of any amount requested.

        Args:
        ----
            address: The XRP address to fund

        Returns:
        -------
            bool: True if successfully funded, False otherwise

        """
        try:
            import httpx

            logger.info(f"Attempting to fund wallet {address} with TestNet XRP")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.XRP_FAUCET_URL,
                    json={"destination": address},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    response_data = response.json()
                    amount_received = response_data.get("amount", 10.0)
                    logger.info(f"Successfully funded wallet {address} with {amount_received} XRP")
                    return True
                else:
                    logger.error(f"Faucet error: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error funding wallet {address}: {e}")
            return False

    def get_wallet_from_secret(self, encrypted_secret: str) -> XRPLWallet:
        """Reconstruct wallet from encrypted secret."""
        try:
            secret = encryption_service.decrypt(encrypted_secret)
            wallet = XRPLWallet.from_seed(secret)
            logger.debug(f"Successfully reconstructed wallet: {wallet.classic_address}")
            return wallet
        except Exception as e:
            logger.error(f"Failed to reconstruct wallet from secret: {e}")
            raise ValueError(f"Invalid encrypted secret: {e}") from e

    def import_wallet(self, private_key_or_seed: str) -> tuple[str, str]:
        """Import an existing wallet from private key or seed phrase.

        Args:
        ----
            private_key_or_seed: The private key or seed phrase to import

        Returns:
        -------
            tuple[str, str]: (address, encrypted_secret)

        Raises:
        ------
            ValueError: If the private key/seed is invalid

        """
        try:
            # Try to create wallet from the input
            # Handle different formats: seed phrase, private key, etc.
            input_str = private_key_or_seed.strip()

            # Try creating wallet from seed first (most common format)
            try:
                wallet = XRPLWallet.from_seed(input_str)
            except Exception:
                # If seed fails, try other formats
                # Check if it looks like a private key (starts with ED, etc.)
                if input_str.startswith(("ED", "sEd", "s")):
                    # Try as secret key
                    wallet = XRPLWallet.from_secret(input_str)
                else:
                    # Try as entropy/seed
                    wallet = XRPLWallet.from_entropy(input_str)

            # Validate the wallet was created successfully
            if not wallet or not wallet.classic_address:
                raise ValueError("Failed to create wallet from provided input")

            # Encrypt the seed for storage
            if not wallet.seed:
                raise ValueError("Wallet seed is missing")

            encrypted_secret = encryption_service.encrypt(wallet.seed)

            return wallet.classic_address, encrypted_secret

        except Exception as e:
            raise ValueError(f"Invalid private key or seed phrase: {str(e)}") from e

    async def validate_testnet_wallet(self, private_key_or_seed: str) -> tuple[str, str, dict]:
        """Validate that a wallet is safe for TestNet import.

        Args:
        ----
            private_key_or_seed: The private key or seed phrase to validate

        Returns:
        -------
            tuple[str, str, dict]: (address, encrypted_secret, validation_info)

        Raises:
        ------
            ValueError: If the wallet is unsafe for TestNet import

        """
        # First, try to import the wallet
        address, encrypted_secret = self.import_wallet(private_key_or_seed)

        # Now perform safety checks
        validation_info = {
            "address": address,
            "is_testnet_safe": False,
            "balance": 0.0,
            "warnings": [],
            "errors": [],
        }

        try:
            # Check balance on both TestNet and MainNet to detect mainnet usage
            testnet_balance = await self.get_balance(address)
            validation_info["balance"] = testnet_balance or 0.0

            # Try to check mainnet balance (switch to mainnet client temporarily)
            mainnet_balance = await self._check_mainnet_balance(address)

            # Safety checks
            if mainnet_balance and mainnet_balance > 0.1:  # More than 0.1 XRP on mainnet
                validation_info["errors"].append(
                    f"This wallet contains {mainnet_balance:.6f} XRP on MainNet. "
                    "For security, we cannot import wallets with MainNet funds."
                )

            # Check for suspicious patterns that suggest mainnet usage
            if mainnet_balance and mainnet_balance > 20:  # High balance suggests real usage
                validation_info["errors"].append(
                    "This wallet appears to be actively used on MainNet. "
                    "Please use a TestNet-only wallet for safety."
                )

            # Add warnings for any mainnet activity
            if mainnet_balance and mainnet_balance > 0:
                validation_info["warnings"].append(
                    f"This wallet has {mainnet_balance:.6f} XRP on MainNet. "
                    "Ensure you're only using TestNet features."
                )

            # Check if wallet has reasonable TestNet balance (not too high)
            balance = validation_info["balance"]
            if (
                isinstance(balance, int | float) and balance > 10000
            ):  # More than 10k TestNet XRP is suspicious
                validation_info["warnings"].append(
                    "This wallet has an unusually high TestNet balance. "
                    "Please verify this is a TestNet-only wallet."
                )

            # If no blocking errors, mark as safe
            if not validation_info["errors"]:
                validation_info["is_testnet_safe"] = True

            return address, encrypted_secret, validation_info

        except Exception as e:
            validation_info["errors"].append(f"Could not validate wallet safety: {str(e)}")
            raise ValueError(f"Wallet validation failed: {str(e)}") from e

    async def _check_mainnet_balance(self, address: str) -> float | None:
        """Check balance on MainNet (temporarily switch networks).

        Args:
        ----
            address: The XRP address to check

        Returns:
        -------
            float | None: Balance in XRP or None if not found/error

        """
        try:
            # Create a temporary mainnet client
            mainnet_client = AsyncJsonRpcClient("https://xrplcluster.com/")

            request = AccountInfo(account=address, ledger_index="validated")
            response = await mainnet_client.request(request)

            if response.is_successful():
                balance_drops = response.result["account_data"]["Balance"]
                return float(drops_to_xrp(balance_drops))
            else:
                # Account not found on mainnet is actually good (means no mainnet funds)
                return None

        except Exception:
            # If we can't check mainnet, assume no balance (safer default)
            return None

    async def get_balance(self, address: str) -> float | None:
        """Get XRP balance for an address.

        Returns balance in XRP (not drops).
        """
        try:
            # Create account info request
            request = AccountInfo(account=address, ledger_index="validated")

            # Get response
            response = await self.client.request(request)

            if response.is_successful():
                # Convert drops to XRP
                balance_drops = response.result["account_data"]["Balance"]
                balance_xrp = float(drops_to_xrp(balance_drops))
                return balance_xrp
            else:
                logger.warning(f"Failed to get balance for {address}: {response.result}")
                return None

        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            # For new accounts that aren't activated yet
            if "Account not found" in str(e):
                return 0.0
            return None

    async def send_xrp(
        self,
        from_encrypted_secret: str,
        to_address: str,
        amount: float,
        memo: str | None = None,
    ) -> dict[str, Any]:
        """Send XRP from one address to another.

        Args:
        ----
            from_encrypted_secret: Encrypted secret of sender
            to_address: Recipient's XRP address
            amount: Amount in XRP to send
            memo: Optional transaction memo

        Returns:
        -------
            Dictionary with transaction result

        """
        try:
            # Validate amount
            if amount <= 0:
                return {"success": False, "error": "Amount must be positive"}

            # Get sender wallet
            wallet = self.get_wallet_from_secret(from_encrypted_secret)

            # Check sender balance
            sender_balance = await self.get_balance(wallet.classic_address)
            if sender_balance is None:
                logger.error(f"Unable to get balance for wallet {wallet.classic_address}")
                return {"success": False, "error": "Unable to verify balance"}

            # Convert to Decimal for precise calculations
            balance_decimal = Decimal(str(sender_balance))
            amount_decimal = Decimal(str(amount))

            # Check available balance (total - reserve - fee)
            required_balance = amount_decimal + STANDARD_FEE + ACCOUNT_RESERVE
            if balance_decimal < required_balance:
                available = max(balance_decimal - ACCOUNT_RESERVE - STANDARD_FEE, Decimal("0"))
                logger.warning(
                    f"Insufficient balance: has {balance_decimal}, "
                    f"needs {required_balance}, available {available}"
                )
                return {
                    "success": False,
                    "error": (
                        f"Insufficient balance. Available: {available} XRP "
                        f"(Reserve: {ACCOUNT_RESERVE} XRP must remain)"
                    ),
                }

            # Create payment transaction (let autofill set Fee/Sequence/LastLedgerSequence)
            if memo:
                # Create payment with memo
                payment = Payment(
                    account=wallet.classic_address,
                    destination=to_address,
                    amount=xrp_to_drops(amount),
                    memos=[
                        Memo(
                            memo_data=memo.encode("utf-8").hex().upper(),
                            memo_type=b"text/plain".hex().upper(),
                        )
                    ],
                )
            else:
                # Create payment without memo
                payment = Payment(
                    account=wallet.classic_address,
                    destination=to_address,
                    amount=xrp_to_drops(amount),
                )

            # Autofill required fields then sign
            prepared = await autofill(payment, self.client)
            signed_tx = sign(prepared, wallet)

            # Submit and wait for validation (reliable submission)
            response = await submit_and_wait(signed_tx, self.client)

            if response.is_successful():
                result = response.result
                # Try both top-level and tx_json fields for returned data
                tx_json = result.get("tx_json") or {}
                fee_drops = result.get("Fee") or tx_json.get("Fee") or "0"
                tx_hash = result.get("hash") or tx_json.get("hash")
                ledger_index = result.get("ledger_index") or tx_json.get("ledger_index")

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "ledger_index": ledger_index,
                    "fee": float(drops_to_xrp(fee_drops)),
                    "amount": amount,
                }
            else:
                return {
                    "success": False,
                    "error": response.result.get("engine_result_message", "Transaction failed"),
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_transaction_history(self, address: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get transaction history for an address.

        Args:
        ----
            address: XRP address
            limit: Maximum number of transactions to return

        Returns:
        -------
            List of transactions

        """
        try:
            # Create account transactions request
            request = AccountTx(account=address, limit=limit)

            # Get response
            response = await self.client.request(request)

            if response.is_successful():
                transactions = []
                for tx in response.result.get("transactions", []):
                    tx_info = tx.get("tx", {})

                    # Parse transaction
                    parsed_tx = {
                        "hash": tx_info.get("hash"),
                        "type": tx_info.get("TransactionType"),
                        "amount": (
                            float(drops_to_xrp(tx_info.get("Amount", "0")))
                            if isinstance(tx_info.get("Amount"), str)
                            else 0
                        ),
                        "fee": float(drops_to_xrp(tx_info.get("Fee", "0"))),
                        "sender": tx_info.get("Account"),
                        "recipient": tx_info.get("Destination"),
                        "timestamp": tx_info.get("date"),
                        "result": tx.get("meta", {}).get("TransactionResult"),
                        "ledger_index": tx_info.get("ledger_index"),
                    }
                    transactions.append(parsed_tx)

                return transactions
            else:
                logger.warning(f"Failed to get transactions for {address}: {response.result}")
                return []

        except Exception as e:
            logger.error(f"Error getting transaction history for {address}: {e}")
            return []

    def validate_address(self, address: str) -> bool:
        """Validate if a string is a valid XRP address."""
        try:
            # XRP addresses start with 'r' and are 25-34 characters
            if not address.startswith("r"):
                return False

            if len(address) < 25 or len(address) > 34:
                return False

            # Try to decode the address
            import re

            pattern = r"^r[a-zA-Z0-9]{24,33}$"
            return bool(re.match(pattern, address))

        except Exception as e:
            logger.error(f"Error validating address {address}: {e}")
            return False

    async def wait_for_transaction(self, tx_hash: str, timeout: int = 60) -> dict[str, Any] | None:
        """Wait for a transaction to be validated.

        Args:
        ----
            tx_hash: Transaction hash to monitor
            timeout: Maximum seconds to wait

        Returns:
        -------
            Transaction result or None if timeout

        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # Check transaction status
                from xrpl.models.requests import Tx

                request = Tx(transaction=tx_hash)
                response = await self.client.request(request)

                if response.is_successful():
                    result = response.result
                    if result.get("validated"):
                        return result

                # Wait before checking again
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error checking transaction {tx_hash}: {e}")
                await asyncio.sleep(2)

        return None


# Global XRP service instance
xrp_service = XRPService()
