import asyncio
import json
from typing import Optional, Dict, Any, Tuple, List
from decimal import Decimal
import xrpl
from xrpl.clients import JsonRpcClient, WebsocketClient
from xrpl.wallet import Wallet, generate
from xrpl.models.transactions import Payment
from xrpl.models.requests import AccountInfo, AccountTx, Tx
from xrpl.transaction import sign, submit_and_wait, autofill_and_sign
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.ledger import get_latest_validated_ledger_sequence
import httpx

from ..config import settings
from ..utils.encryption import get_encryption_service

class XRPService:
    """Service for interacting with XRP Ledger"""
    
    def __init__(self):
        """Initialize XRP client connections"""
        # Convert WSS URL to HTTPS for JSON-RPC
        self.json_rpc_url = settings.XRP_JSON_RPC_URL
        self.websocket_url = settings.XRP_WEBSOCKET_URL
        self.network = settings.XRP_NETWORK
        self.client = JsonRpcClient(self.json_rpc_url)
        self.encryption = get_encryption_service()
    
    def create_wallet(self) -> Tuple[str, str]:
        """
        Create a new XRP wallet
        Returns: (address, encrypted_secret)
        """
        # Generate new wallet
        wallet = generate()
        
        # Encrypt the secret key
        encrypted_secret = self.encryption.encrypt(wallet.seed)
        
        return wallet.classic_address, encrypted_secret
    
    async def fund_wallet_from_faucet(self, address: str) -> Dict[str, Any]:
        """
        Fund a TestNet wallet using the XRP faucet
        Returns dict with success status and details
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.XRP_FAUCET_URL,
                    json={"destination": address},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Funded wallet {address} with TestNet XRP")
                    return {
                        "success": True,
                        "amount": data.get("amount", 10000),
                        "balance": data.get("balance")
                    }
                else:
                    print(f"❌ Faucet error: {response.text}")
                    return {
                        "success": False,
                        "error": f"Faucet returned status {response.status_code}"
                    }
        except Exception as e:
            print(f"❌ Error funding wallet: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_wallet_from_secret(self, encrypted_secret: str) -> Wallet:
        """Reconstruct wallet from encrypted secret"""
        secret = self.encryption.decrypt(encrypted_secret)
        return Wallet.from_seed(secret)
    
    async def get_balance(self, address: str) -> Optional[float]:
        """
        Get XRP balance for an address
        Returns balance in XRP (not drops)
        """
        try:
            # Create account info request
            request = AccountInfo(
                account=address,
                ledger_index="validated"
            )
            
            # Get response
            response = self.client.request(request)
            
            if response.is_successful():
                # Convert drops to XRP
                balance_drops = response.result["account_data"]["Balance"]
                balance_xrp = float(drops_to_xrp(balance_drops))
                return balance_xrp
            else:
                print(f"⚠️ Error getting balance: {response.result}")
                # Account might not be activated yet
                if "Account not found" in str(response.result):
                    return 0.0
                return None
                
        except Exception as e:
            print(f"❌ Error getting balance: {str(e)}")
            # For new accounts that aren't activated yet
            if "Account not found" in str(e):
                return 0.0
            return None
    
    async def send_xrp(
        self,
        from_encrypted_secret: str,
        to_address: str,
        amount: float,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send XRP from one address to another
        
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
            
            # Minimum XRP that can be sent
            if amount < 0.000001:
                return {
                    "success": False,
                    "error": "Amount too small (minimum is 0.000001 XRP)"
                }
            
            # Get sender wallet
            wallet = self.get_wallet_from_secret(from_encrypted_secret)
            
            # Check sender balance
            sender_balance = await self.get_balance(wallet.classic_address)
            if sender_balance is None:
                return {
                    "success": False,
                    "error": "Could not retrieve sender balance"
                }
            
            # Account for transaction fee (10 drops = 0.00001 XRP)
            total_needed = amount + 0.00002  # Add some buffer for fee
            if sender_balance < total_needed:
                return {
                    "success": False,
                    "error": f"Insufficient balance. Have {sender_balance} XRP, need {total_needed} XRP"
                }
            
            # Create payment transaction
            payment = Payment(
                account=wallet.classic_address,
                destination=to_address,
                amount=xrp_to_drops(amount),
            )
            
            # Autofill and sign transaction
            signed_tx = autofill_and_sign(payment, self.client, wallet)
            
            # Submit and wait for validation
            response = submit_and_wait(signed_tx, self.client)
            
            if response.is_successful():
                result = response.result
                tx_hash = result.get("hash")
                
                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "ledger_index": result.get("ledger_index"),
                    "fee": float(drops_to_xrp(result.get("Fee", "10"))),
                    "amount": amount,
                    "sender": wallet.classic_address,
                    "recipient": to_address
                }
            else:
                return {
                    "success": False,
                    "error": response.result.get("engine_result_message", "Transaction failed")
                }
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Send XRP error: {error_msg}")
            
            # Provide more user-friendly error messages
            if "tecUNFUNDED_PAYMENT" in error_msg:
                return {
                    "success": False,
                    "error": "Insufficient XRP balance to complete transaction"
                }
            elif "tecNO_DST" in error_msg:
                return {
                    "success": False,
                    "error": "Recipient account does not exist or is not activated"
                }
            elif "temBAD_FEE" in error_msg:
                return {
                    "success": False,
                    "error": "Invalid transaction fee"
                }
            else:
                return {
                    "success": False,
                    "error": error_msg
                }
    
    async def get_transaction_history(
        self,
        address: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for an address
        
        Args:
            address: XRP address
            limit: Maximum number of transactions to return
        
        Returns:
            List of transactions
        """
        try:
            # Create account transactions request
            request = AccountTx(
                account=address,
                limit=limit
            )
            
            # Get response
            response = self.client.request(request)
            
            if response.is_successful():
                transactions = []
                for tx in response.result.get("transactions", []):
                    tx_info = tx.get("tx", {})
                    
                    # Determine if this address was sender or receiver
                    is_sender = tx_info.get("Account") == address
                    
                    # Parse transaction
                    parsed_tx = {
                        "hash": tx_info.get("hash"),
                        "type": tx_info.get("TransactionType"),
                        "amount": float(drops_to_xrp(tx_info.get("Amount", "0")))
                            if isinstance(tx_info.get("Amount"), str) else 0,
                        "fee": float(drops_to_xrp(tx_info.get("Fee", "0"))),
                        "sender": tx_info.get("Account"),
                        "recipient": tx_info.get("Destination"),
                        "timestamp": tx_info.get("date"),
                        "result": tx.get("meta", {}).get("TransactionResult"),
                        "ledger_index": tx_info.get("ledger_index"),
                        "is_sender": is_sender,
                        "direction": "out" if is_sender else "in"
                    }
                    transactions.append(parsed_tx)
                
                return transactions
            else:
                print(f"⚠️ Error getting transactions: {response.result}")
                return []
                
        except Exception as e:
            print(f"❌ Error getting transaction history: {str(e)}")
            return []
    
    async def get_transaction_details(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific transaction by hash"""
        try:
            request = Tx(transaction=tx_hash)
            response = self.client.request(request)
            
            if response.is_successful():
                result = response.result
                return {
                    "hash": result.get("hash"),
                    "ledger_index": result.get("ledger_index"),
                    "amount": float(drops_to_xrp(result.get("Amount", "0")))
                        if isinstance(result.get("Amount"), str) else 0,
                    "fee": float(drops_to_xrp(result.get("Fee", "0"))),
                    "sender": result.get("Account"),
                    "recipient": result.get("Destination"),
                    "validated": result.get("validated", False),
                    "timestamp": result.get("date")
                }
            return None
        except Exception as e:
            print(f"❌ Error getting transaction details: {str(e)}")
            return None
    
    def validate_address(self, address: str) -> bool:
        """
        Validate if a string is a valid XRP address
        """
        try:
            # XRP addresses start with 'r' and are 25-34 characters
            if not address or not address.startswith('r'):
                return False
            
            if len(address) < 25 or len(address) > 34:
                return False
            
            # Check if it contains only valid characters
            import re
            pattern = r'^r[a-zA-Z0-9]{24,33}$'
            return bool(re.match(pattern, address))
            
        except Exception:
            return False
    
    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a transaction to be validated
        
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
                result = await self.get_transaction_details(tx_hash)
                if result and result.get("validated"):
                    return result
                
                # Wait before checking again
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Error checking transaction: {str(e)}")
                await asyncio.sleep(2)
        
        return None

# Global XRP service instance
xrp_service = XRPService()