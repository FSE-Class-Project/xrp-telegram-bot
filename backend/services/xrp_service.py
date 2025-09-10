"""XRP Ledger integration service."""

from __future__ import annotations

import asyncio
from typing import Any

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import sign, submit_and_wait
from xrpl.models.requests import AccountInfo, AccountTx
from xrpl.models.transactions import Payment
from xrpl.utils import drops_to_xrp, xrp_to_drops
from xrpl.wallet import Wallet  # Remove 'generate' import - it's deprecated

from ..config import settings
from ..utils.encryption import encryption_service


class XRPService:
    """Service for interacting with XRP Ledger."""

    def __init__(self):
        """Initialize XRP client connections."""
        self.json_rpc_url = settings.XRP_JSON_RPC_URL
        self.websocket_url = settings.XRP_WEBSOCKET_URL
        self.network = settings.XRP_NETWORK
        self.client = AsyncJsonRpcClient(self.json_rpc_url)

    def create_wallet(self) -> tuple[str, str]:
        """
        Create a new XRP wallet.
        Returns: (address, encrypted_secret)
        """
        # Use Wallet.create() instead of generate() for xrpl-py 2.5.0
        wallet = Wallet.create()

        # Ensure seed exists before encrypting
        if not wallet.seed:
            raise ValueError("Wallet seed is None - cannot create wallet")

        # Encrypt the secret key (use seed instead of secret)
        encrypted_secret = encryption_service.encrypt(wallet.seed)

        return wallet.classic_address, encrypted_secret

    async def fund_wallet_from_faucet(self, address: str) -> bool:
        """
        Fund a TestNet wallet using the XRP faucet.
        """
        try:
            # For TestNet, use the faucet API
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.XRP_FAUCET_URL, json={"destination": address}, timeout=30.0
                )

                if response.status_code == 200:
                    print(f"Funded wallet {address} with TestNet XRP")
                    return True
                else:
                    print(f"Faucet error: {response.text}")
                    return False
        except Exception as e:
            print(f"Error funding wallet: {str(e)}")
            return False

    def get_wallet_from_secret(self, encrypted_secret: str) -> Wallet:
        """Reconstruct wallet from encrypted secret."""
        secret = encryption_service.decrypt(encrypted_secret)
        return Wallet.from_seed(secret)

    async def get_balance(self, address: str) -> float | None:
        """
        Get XRP balance for an address.
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
                print(f"Error getting balance: {response.result}")
                return None

        except Exception as e:
            print(f"Error getting balance: {str(e)}")
            # For new accounts that aren't activated yet
            if "Account not found" in str(e):
                return 0.0
            return None

    async def send_xrp(
        self, from_encrypted_secret: str, to_address: str, amount: float, memo: str | None = None
    ) -> dict[str, Any]:
        """
        Send XRP from one address to another.

        Args:
            from_encrypted_secret: Encrypted secret of sender
            to_address: Recipient's XRP address
            amount: Amount in XRP to send
            memo: Optional transaction memo

        Returns:
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
            if sender_balance is None or sender_balance < amount + 0.00001:
                return {"success": False, "error": "Insufficient balance"}

            # Create payment transaction
            payment = Payment(
                account=wallet.classic_address,
                destination=to_address,
                amount=xrp_to_drops(amount),
                fee="10",  # 10 drops = 0.00001 XRP
            )

            # Sign and submit transaction
            signed_tx = sign(payment, wallet)

            # Submit and wait for validation
            response = await submit_and_wait(signed_tx, self.client)

            if response.is_successful():
                result = response.result
                return {
                    "success": True,
                    "tx_hash": result.get("hash"),
                    "ledger_index": result.get("ledger_index"),
                    "fee": float(drops_to_xrp(result.get("Fee", "0"))),
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
        """
        Get transaction history for an address.

        Args:
            address: XRP address
            limit: Maximum number of transactions to return

        Returns:
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
                print(f"Error getting transactions: {response.result}")
                return []

        except Exception as e:
            print(f"Error getting transaction history: {str(e)}")
            return []

    def validate_address(self, address: str) -> bool:
        """
        Validate if a string is a valid XRP address.
        """
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

        except Exception:
            return False

    async def wait_for_transaction(self, tx_hash: str, timeout: int = 60) -> dict[str, Any] | None:
        """
        Wait for a transaction to be validated.

        Args:
            tx_hash: Transaction hash to monitor
            timeout: Maximum seconds to wait

        Returns:
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
                print(f"Error checking transaction: {str(e)}")
                await asyncio.sleep(2)

        return None


# Global XRP service instance
xrp_service = XRPService()
