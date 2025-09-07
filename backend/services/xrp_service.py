"""XRP Ledger integration service with modern Python typing."""
from __future__ import annotations
import asyncio
import logging
from typing import Any
import re

# xrpl library doesn't have complete type stubs, so we need type: ignore
from xrpl.clients import JsonRpcClient  # type: ignore[import-untyped]
from xrpl.wallet import Wallet, generate  # type: ignore[import-untyped]
from xrpl.models.transactions import Payment  # type: ignore[import-untyped]
from xrpl.models.transactions.metadata import Memo  # type: ignore[import-untyped]
from xrpl.models.requests import AccountInfo, AccountTx, Tx  # type: ignore[import-untyped]
from xrpl.transaction import sign, submit_and_wait  # type: ignore[import-untyped]
from xrpl.utils import xrp_to_drops, drops_to_xrp  # type: ignore[import-untyped]
import httpx

from ..config import settings
from ..utils.encryption import encryption_service

logger = logging.getLogger(__name__)


class XRPService:
    """Service for interacting with XRP Ledger."""
    
    def __init__(self) -> None:
        """Initialize XRP client connections."""
        self.json_rpc_url: str = settings.XRP_JSON_RPC_URL
        self.websocket_url: str = settings.XRP_WEBSOCKET_URL
        self.network: str = settings.XRP_NETWORK
        self.client: Any = JsonRpcClient(self.json_rpc_url)  # type: ignore[no-untyped-call]
    
    def create_wallet(self) -> tuple[str, str]:
        """Create a new XRP wallet.
        
        Returns:
            Tuple of (address, encrypted_secret)
        """
        wallet: Any = generate()  # type: ignore[no-untyped-call]
        
        # Encrypt the secret key
        encrypted_secret = encryption_service.encrypt(wallet.seed)  # type: ignore[attr-defined]
        
        logger.info(f"Created new wallet: {wallet.classic_address}")  # type: ignore[attr-defined]
        return wallet.classic_address, encrypted_secret  # type: ignore[attr-defined, return-value]
    
    async def fund_wallet_from_faucet(
        self, 
        address: str,
        amount: int = 100
    ) -> bool:
        """Fund a TestNet wallet using the XRP faucet.
        
        Args:
            address: XRP address to fund
            amount: Amount of XRP to request (TestNet only)
            
        Returns:
            True if funding successful, False otherwise
        """
        if self.network != "testnet":
            logger.warning("Faucet funding only available on TestNet")
            return False
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    settings.XRP_FAUCET_URL,
                    json={"destination": address, "amount": str(amount)}
                )
                
                if response.status_code == 200:
                    logger.info(f"Funded wallet {address} with {amount} TestNet XRP")
                    return True
                else:
                    logger.error(f"Faucet error: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error funding wallet: {str(e)}")
            return False
    
    def get_wallet_from_secret(self, encrypted_secret: str) -> Any:
        """Reconstruct wallet from encrypted secret.
        
        Args:
            encrypted_secret: Encrypted wallet secret
            
        Returns:
            Wallet instance
        """
        secret: str = encryption_service.decrypt(encrypted_secret)
        wallet: Any = Wallet.from_seed(secret)  # type: ignore[no-untyped-call, attr-defined]
        return wallet
    
    async def get_balance(self, address: str) -> float | None:
        """Get XRP balance for an address.
        
        Args:
            address: XRP address to check
            
        Returns:
            Balance in XRP or None if error
        """
        try:
            request: Any = AccountInfo(  # type: ignore[no-untyped-call]
                account=address,
                ledger_index="validated"
            )
            
            response: Any = self.client.request(request)  # type: ignore[attr-defined]
            
            if response.is_successful():  # type: ignore[attr-defined]
                balance_drops: str = response.result["account_data"]["Balance"]  # type: ignore[attr-defined]
                balance_xrp: float = float(drops_to_xrp(balance_drops))  # type: ignore[no-untyped-call]
                return balance_xrp
            else:
                logger.error(f"Error getting balance: {response.result}")  # type: ignore[attr-defined]
                return None
                
        except Exception as e:
            # For new accounts that aren't activated yet
            if "Account not found" in str(e):
                return 0.0
            
            logger.error(f"Error getting balance: {str(e)}")
            return None
    
    async def send_xrp(
        self,
        from_encrypted_secret: str,
        to_address: str,
        amount: float,
        memo: str | None = None
    ) -> dict[str, Any]:
        """Send XRP from one address to another.
        
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
                return {
                    "success": False,
                    "error": "Amount must be positive"
                }
            
            # Validate recipient address
            if not self.validate_address(to_address):
                return {
                    "success": False,
                    "error": f"Invalid XRP address: {to_address}"
                }
            
            # Get sender wallet
            wallet: Any = self.get_wallet_from_secret(from_encrypted_secret)
            
            # Check sender balance
            sender_balance = await self.get_balance(wallet.classic_address)  # type: ignore[attr-defined]
            if sender_balance is None or sender_balance < amount + 0.00001:
                return {
                    "success": False,
                    "error": f"Insufficient balance. Available: {sender_balance} XRP"
                }
            
            # Create payment transaction
            payment: Any = Payment(  # type: ignore[no-untyped-call]
                account=wallet.classic_address,  # type: ignore[attr-defined]
                destination=to_address,
                amount=xrp_to_drops(amount),  # type: ignore[no-untyped-call]
                fee="10",  # 10 drops = 0.00001 XRP
            )
            
            # Add memo if provided
            if memo:
                payment.memos = [  # type: ignore[attr-defined]
                    Memo(  # type: ignore[no-untyped-call]
                        memo_data=memo.encode('utf-8').hex()
                    )
                ]
            
            # Sign and submit transaction
            signed_tx: Any = sign(payment, wallet)  # type: ignore[no-untyped-call]
            response: Any = submit_and_wait(signed_tx, self.client)  # type: ignore[no-untyped-call]
            
            if response.is_successful():  # type: ignore[attr-defined]
                result: Any = response.result  # type: ignore[attr-defined]
                return {
                    "success": True,
                    "tx_hash": result.get("hash"),  # type: ignore[attr-defined]
                    "ledger_index": result.get("ledger_index"),  # type: ignore[attr-defined]
                    "fee": float(drops_to_xrp(result.get("Fee", "0"))),  # type: ignore[no-untyped-call, attr-defined]
                    "amount": amount
                }
            else:
                return {
                    "success": False,
                    "error": response.result.get("engine_result_message", "Transaction failed")  # type: ignore[attr-defined]
                }
                
        except Exception as e:
            logger.error(f"Transaction error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_transaction_history(
        self,
        address: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get transaction history for an address.
        
        Args:
            address: XRP address
            limit: Maximum number of transactions to return
            
        Returns:
            List of transaction details
        """
        try:
            request: Any = AccountTx(  # type: ignore[no-untyped-call]
                account=address,
                limit=limit
            )
            
            response: Any = self.client.request(request)  # type: ignore[attr-defined]
            
            if response.is_successful():  # type: ignore[attr-defined]
                transactions: list[dict[str, Any]] = []
                
                for tx in response.result.get("transactions", []):  # type: ignore[attr-defined]
                    tx_info: dict[str, Any] = tx.get("tx", {})  # type: ignore[assignment]
                    
                    # Parse amount (handle different formats)
                    amount_raw = tx_info.get("Amount", "0")
                    if isinstance(amount_raw, str):
                        amount = float(drops_to_xrp(amount_raw))  # type: ignore[no-untyped-call]
                    elif isinstance(amount_raw, dict):
                        # Token amount (not XRP)
                        amount = float(amount_raw.get("value", "0"))
                    else:
                        amount = 0.0
                    
                    parsed_tx: dict[str, Any] = {
                        "hash": tx_info.get("hash", ""),
                        "type": tx_info.get("TransactionType", "Unknown"),
                        "amount": amount,
                        "fee": float(drops_to_xrp(tx_info.get("Fee", "0"))),  # type: ignore[no-untyped-call]
                        "sender": tx_info.get("Account", ""),
                        "recipient": tx_info.get("Destination"),
                        "timestamp": tx_info.get("date"),
                        "result": tx.get("meta", {}).get("TransactionResult"),  # type: ignore[attr-defined]
                        "ledger_index": tx_info.get("ledger_index")
                    }
                    transactions.append(parsed_tx)
                
                return transactions
            else:
                logger.error(f"Error getting transactions: {response.result}")  # type: ignore[attr-defined]
                return []
                
        except Exception as e:
            logger.error(f"Error getting transaction history: {str(e)}")
            return []
    
    def validate_address(self, address: str) -> bool:
        """Validate if a string is a valid XRP address.
        
        Args:
            address: String to validate
            
        Returns:
            True if valid XRP address, False otherwise
        """
        # XRP addresses start with 'r' and are 25-34 characters
        if not address or not address.startswith('r'):
            return False
        
        if len(address) < 25 or len(address) > 34:
            return False
        
        # Valid base58 characters for XRP addresses
        pattern = r'^r[1-9A-HJ-NP-Za-km-z]{24,33}$'
        return bool(re.match(pattern, address))
    
    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout: int = 60
    ) -> dict[str, Any] | None:
        """Wait for a transaction to be validated.
        
        Args:
            tx_hash: Transaction hash to monitor
            timeout: Maximum seconds to wait
            
        Returns:
            Transaction result or None if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                request: Any = Tx(transaction=tx_hash)  # type: ignore[no-untyped-call]
                response: Any = self.client.request(request)  # type: ignore[attr-defined]
                
                if response.is_successful():  # type: ignore[attr-defined]
                    result: dict[str, Any] = response.result  # type: ignore[attr-defined]
                    if result.get("validated"):
                        return result
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error checking transaction: {str(e)}")
                await asyncio.sleep(2)
        
        return None


# Global XRP service instance
xrp_service = XRPService()