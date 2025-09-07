from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from ..database.models import User, Wallet, Transaction
from ..services.xrp_service import xrp_service
from ..utils.encryption import get_encryption_service

class UserService:
    """Service for managing users and wallets"""
    
    @staticmethod
    async def create_user(
        db: Session,
        telegram_id: str,
        telegram_username: Optional[str] = None,
        telegram_first_name: Optional[str] = None,
        telegram_last_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user with an XRP wallet
        Returns dict with user info and wallet details
        """
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(
                User.telegram_id == str(telegram_id)
            ).first()
            
            if existing_user:
                # User exists, get their wallet
                wallet = db.query(Wallet).filter(
                    Wallet.user_id == existing_user.id
                ).first()
                
                if wallet:
                    # Update balance
                    balance = await xrp_service.get_balance(wallet.xrp_address)
                    if balance is not None:
                        wallet.balance = balance
                        db.commit()
                    
                    return {
                        "success": True,
                        "user_id": existing_user.id,
                        "telegram_id": existing_user.telegram_id,
                        "xrp_address": wallet.xrp_address,
                        "balance": wallet.balance,
                        "is_new": False
                    }
            
            # Create new user
            user = User(
                telegram_id=str(telegram_id),
                telegram_username=telegram_username,
                telegram_first_name=telegram_first_name,
                telegram_last_name=telegram_last_name
            )
            
            db.add(user)
            db.flush()  # Get user ID without committing
            
            # Create XRP wallet
            address, encrypted_secret = xrp_service.create_wallet()
            
            wallet = Wallet(
                user_id=user.id,
                xrp_address=address,
                encrypted_secret=encrypted_secret,
                balance=0.0,
                last_balance_update=datetime.utcnow()
            )
            
            db.add(wallet)
            db.commit()
            db.refresh(user)
            db.refresh(wallet)
            
            # Fund wallet from faucet (async operation)
            funding_result = await xrp_service.fund_wallet_from_faucet(address)
            
            if funding_result["success"]:
                # Update balance after funding
                balance = await xrp_service.get_balance(address)
                if balance is not None:
                    wallet.balance = balance
                    wallet.last_balance_update = datetime.utcnow()
                    db.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "xrp_address": wallet.xrp_address,
                "balance": wallet.balance,
                "is_new": True,
                "funding_success": funding_result["success"]
            }
            
        except Exception as e:
            print(f"❌ Error creating user: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_user_by_telegram_id(
        db: Session,
        telegram_id: str
    ) -> Optional[User]:
        """Get user by Telegram ID"""
        return db.query(User).filter(
            User.telegram_id == str(telegram_id)
        ).first()
    
    @staticmethod
    def get_user_wallet(
        db: Session,
        user: User
    ) -> Optional[Wallet]:
        """Get user's wallet"""
        return db.query(Wallet).filter(
            Wallet.user_id == user.id
        ).first()
    
    @staticmethod
    def get_user_by_xrp_address(
        db: Session,
        xrp_address: str
    ) -> Optional[User]:
        """Get user by XRP address"""
        wallet = db.query(Wallet).filter(
            Wallet.xrp_address == xrp_address
        ).first()
        
        if wallet:
            return db.query(User).filter(
                User.id == wallet.user_id
            ).first()
        return None
    
    @staticmethod
    async def update_balance(
        db: Session,
        user: User
    ) -> float:
        """
        Update user's wallet balance from blockchain
        """
        wallet = UserService.get_user_wallet(db, user)
        if not wallet:
            raise ValueError("User has no wallet")
        
        # Get balance from XRP Ledger
        balance = await xrp_service.get_balance(wallet.xrp_address)
        
        if balance is not None:
            wallet.balance = balance
            wallet.last_balance_update = datetime.utcnow()
            db.commit()
            return balance
        
        return wallet.balance
    
    @staticmethod
    async def send_xrp(
        db: Session,
        sender: User,
        recipient_address: str,
        amount: float,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send XRP from user to another address
        """
        try:
            # Get sender's wallet
            sender_wallet = UserService.get_user_wallet(db, sender)
            if not sender_wallet:
                return {
                    "success": False,
                    "error": "Sender has no wallet"
                }
            
            # Validate recipient address
            if not xrp_service.validate_address(recipient_address):
                return {
                    "success": False,
                    "error": "Invalid recipient address format"
                }
            
            # Check if sending to self
            if sender_wallet.xrp_address == recipient_address:
                return {
                    "success": False,
                    "error": "Cannot send XRP to yourself"
                }
            
            # Check if recipient is internal user
            recipient_wallet = db.query(Wallet).filter(
                Wallet.xrp_address == recipient_address
            ).first()
            
            # Send transaction on XRP Ledger
            result = await xrp_service.send_xrp(
                from_encrypted_secret=sender_wallet.encrypted_secret,
                to_address=recipient_address,
                amount=amount,
                memo=memo
            )
            
            if result["success"]:
                # Record transaction in database
                transaction = Transaction(
                    sender_id=sender.id,
                    sender_address=sender_wallet.xrp_address,
                    recipient_address=recipient_address,
                    amount=amount,
                    fee=result.get("fee", 0.00001),
                    tx_hash=result.get("tx_hash"),
                    ledger_index=result.get("ledger_index"),
                    status="confirmed",
                    confirmed_at=datetime.utcnow()
                )
                db.add(transaction)
                
                # Update sender's balance
                await UserService.update_balance(db, sender)
                
                # If internal transfer, update recipient balance too
                if recipient_wallet:
                    recipient_user = db.query(User).filter(
                        User.id == recipient_wallet.user_id
                    ).first()
                    if recipient_user:
                        await UserService.update_balance(db, recipient_user)
                
                db.commit()
                
                return {
                    "success": True,
                    "tx_hash": result.get("tx_hash"),
                    "amount": amount,
                    "fee": result.get("fee"),
                    "sender": result.get("sender"),
                    "recipient": recipient_address
                }
            else:
                # Record failed transaction
                transaction = Transaction(
                    sender_id=sender.id,
                    sender_address=sender_wallet.xrp_address,
                    recipient_address=recipient_address,
                    amount=amount,
                    status="failed",
                    error_message=result.get("error")
                )
                db.add(transaction)
                db.commit()
                
                return result
                
        except Exception as e:
            print(f"❌ Error in send_xrp: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_transaction_history(
        db: Session,
        user: User,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get user's transaction history from database"""
        try:
            wallet = UserService.get_user_wallet(db, user)
            if not wallet:
                return []
            
            # Get transactions where user is sender
            sent_transactions = db.query(Transaction).filter(
                Transaction.sender_id == user.id
            ).order_by(
                Transaction.created_at.desc()
            ).limit(limit).all()
            
            # Get transactions where user is recipient (if we track them)
            received_transactions = db.query(Transaction).filter(
                Transaction.recipient_address == wallet.xrp_address
            ).order_by(
                Transaction.created_at.desc()
            ).limit(limit).all()
            
            # Combine and format transactions
            all_transactions = []
            
            for tx in sent_transactions:
                all_transactions.append({
                    "hash": tx.tx_hash,
                    "type": "sent",
                    "amount": tx.amount,
                    "fee": tx.fee,
                    "address": tx.recipient_address,  # The other party
                    "status": tx.status,
                    "timestamp": tx.created_at.isoformat(),
                    "error": tx.error_message
                })
            
            for tx in received_transactions:
                if tx.sender_id != user.id:  # Don't duplicate sent transactions
                    all_transactions.append({
                        "hash": tx.tx_hash,
                        "type": "received",
                        "amount": tx.amount,
                        "fee": 0,  # Receiver doesn't pay fee
                        "address": tx.sender_address,  # The other party
                        "status": tx.status,
                        "timestamp": tx.created_at.isoformat(),
                        "error": None
                    })
            
            # Sort by timestamp
            all_transactions.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return all_transactions[:limit]
            
        except Exception as e:
            print(f"❌ Error getting transaction history: {str(e)}")
            return []
    
    @staticmethod
    async def get_user_info(
        db: Session,
        telegram_id: str
    ) -> Dict[str, Any]:
        """Get complete user information including wallet"""
        try:
            user = UserService.get_user_by_telegram_id(db, telegram_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            wallet = UserService.get_user_wallet(db, user)
            if not wallet:
                return {
                    "success": False,
                    "error": "Wallet not found"
                }
            
            # Update balance
            balance = await xrp_service.get_balance(wallet.xrp_address)
            if balance is not None:
                wallet.balance = balance
                wallet.last_balance_update = datetime.utcnow()
                db.commit()
            
            # Get transaction count
            tx_count = db.query(Transaction).filter(
                Transaction.sender_id == user.id
            ).count()
            
            return {
                "success": True,
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "xrp_address": wallet.xrp_address,
                "balance": wallet.balance,
                "transaction_count": tx_count,
                "created_at": user.created_at.isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error getting user info: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# Global user service instance
user_service = UserService()