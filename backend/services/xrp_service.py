import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet, generate

from ..config import settings

class XRPService:
    """Service for interacting with XRP Ledger"""
    
    def __init__(self):
        url = settings.XRP_WEBSOCKET_URL.replace("wss://", "https://")
        self.client = JsonRpcClient(url)
    
    def create_wallet(self):
        """Create a new XRP wallet"""
        wallet = generate()
        return wallet.classic_address, wallet.seed
    
    # TODO: Implement more XRP operations

xrp_service = XRPService()
