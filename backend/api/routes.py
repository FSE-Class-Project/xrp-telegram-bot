from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
import httpx

from ..database.connection import get_db
from ..services.user_service import user_service
from ..services.xrp_service import xrp_service
from ..database.models import User, PriceHistory
from ..config import settings

# Create router
router = APIRouter(prefix="/api/v1", tags=["API"])

# ============= Pydantic Models =============

class UserRegistration(BaseModel):
    telegram_id: str
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None

class UserResponse(BaseModel):
    success: bool
    user_id: Optional[int] = None
    telegram_id: Optional[str] = None
    xrp_address: Optional[str] = None
    balance: Optional[float] = None
    is_new: Optional[bool] = None
    error: Optional[str] = None

class SendTransactionRequest(BaseModel):
    from_telegram_id: str
    to_address: str
    amount: float = Field(gt=0, description="Amount must be positive")
    memo: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        if v < 0.000001:
            raise ValueError('Amount too small (minimum is 0.000001 XRP)')
        return v

class TransactionResponse(BaseModel):
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    amount: Optional[float] = None
    fee: Optional[float] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None

class BalanceResponse(BaseModel):
    success: bool
    address: Optional[str] = None
    balance: Optional[float] = None
    last_updated: Optional[str] = None
    error: Optional[str] = None

class PriceResponse(BaseModel):
    success: bool
    price_usd: Optional[float] = None
    change_24h: Optional[float] = None
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

class TransactionHistoryItem(BaseModel):
    hash: Optional[str]
    type: str  # sent or received
    amount: float
    fee: float
    address: str  # The other party
    status: str
    timestamp: str
    error: Optional[str]

class TransactionHistoryResponse(BaseModel):
    success: bool
    transactions: List[TransactionHistoryItem] = []
    error: Optional[str] = None

class UserInfoResponse(BaseModel):
    success: bool
    user_id: Optional[int] = None
    telegram_id: Optional[str] = None
    telegram_username: Optional[str] = None
    xrp_address: Optional[str] = None
    balance: Optional[float] = None
    transaction_count: Optional[int] = None
    created_at: Optional[str] = None
    error: Optional[str] = None

# ============= Health Check =============

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "XRP Telegram Bot API",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "network": settings.XRP_NETWORK
    }

# ============= User Endpoints =============

@router.post("/user/register", response_model=UserResponse)
async def register_user(
    registration: UserRegistration,
    db: Session = Depends(get_db)
):
    """Register a new user and create XRP wallet"""
    try:
        result = await user_service.create_user(
            db=db,
            telegram_id=registration.telegram_id,
            telegram_username=registration.telegram_username,
            telegram_first_name=registration.telegram_first_name,
            telegram_last_name=registration.telegram_last_name
        )
        
        if result["success"]:
            return UserResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create user")
            )
        
    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/user/{telegram_id}", response_model=UserInfoResponse)
async def get_user_info(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """Get user information including wallet details"""
    result = await user_service.get_user_info(db, telegram_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "User not found")
        )
    
    return UserInfoResponse(**result)

# ============= Wallet Endpoints =============

@router.get("/wallet/balance/{telegram_id}", response_model=BalanceResponse)
async def get_balance(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """Get user's XRP balance"""
    try:
        user = user_service.get_user_by_telegram_id(db, telegram_id)
        
        if not user:
            return BalanceResponse(
                success=False,
                error="User not found"
            )
        
        wallet = user_service.get_user_wallet(db, user)
        if not wallet:
            return BalanceResponse(
                success=False,
                error="Wallet not found"
            )
        
        # Update balance from blockchain
        balance = await user_service.update_balance(db, user)
        
        return BalanceResponse(
            success=True,
            address=wallet.xrp_address,
            balance=balance,
            last_updated=wallet.last_balance_update.isoformat() 
                if wallet.last_balance_update else None
        )
        
    except Exception as e:
        print(f"❌ Balance check error: {str(e)}")
        return BalanceResponse(
            success=False,
            error=str(e)
        )

@router.get("/wallet/validate/{address}")
async def validate_address(address: str):
    """Validate an XRP address format"""
    is_valid = xrp_service.validate_address(address)
    return {
        "address": address,
        "is_valid": is_valid
    }

# ============= Transaction Endpoints =============

@router.post("/transaction/send", response_model=TransactionResponse)
async def send_transaction(
    request: SendTransactionRequest,
    db: Session = Depends(get_db)
):
    """Send XRP to another address"""
    try:
        # Get sender
        sender = user_service.get_user_by_telegram_id(db, request.from_telegram_id)
        
        if not sender:
            return TransactionResponse(
                success=False,
                error="Sender not found"
            )
        
        # Send transaction
        result = await user_service.send_xrp(
            db=db,
            sender=sender,
            recipient_address=request.to_address,
            amount=request.amount,
            memo=request.memo
        )
        
        return TransactionResponse(**result)
        
    except Exception as e:
        print(f"❌ Send transaction error: {str(e)}")
        return TransactionResponse(
            success=False,
            error=str(e)
        )

@router.get("/transaction/history/{telegram_id}", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    telegram_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get user's transaction history"""
    try:
        user = user_service.get_user_by_telegram_id(db, telegram_id)
        
        if not user:
            return TransactionHistoryResponse(
                success=False,
                error="User not found"
            )
        
        history = user_service.get_transaction_history(db, user, limit)
        
        # Convert to response model
        transactions = [TransactionHistoryItem(**tx) for tx in history]
        
        return TransactionHistoryResponse(
            success=True,
            transactions=transactions
        )
        
    except Exception as e:
        print(f"❌ Transaction history error: {str(e)}")
        return TransactionHistoryResponse(
            success=False,
            error=str(e)
        )

@router.get("/transaction/{tx_hash}")
async def get_transaction_details(tx_hash: str):
    """Get details of a specific transaction"""
    try:
        details = await xrp_service.get_transaction_details(tx_hash)
        if details:
            return {
                "success": True,
                **details
            }
        else:
            return {
                "success": False,
                "error": "Transaction not found"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============= Price Endpoints =============

@router.get("/price/current", response_model=PriceResponse)
async def get_current_price(db: Session = Depends(get_db)):
    """Get current XRP price from CoinGecko"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.PRICE_API_URL}/simple/price",
                params={
                    "ids": "ripple",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                ripple_data = data.get("ripple", {})
                
                # Cache the price in database
                price_record = PriceHistory(
                    price_usd=ripple_data.get("usd", 0),
                    change_24h=ripple_data.get("usd_24h_change", 0),
                    market_cap=ripple_data.get("usd_market_cap", 0),
                    volume_24h=ripple_data.get("usd_24h_vol", 0),
                    source="coingecko"
                )
                db.add(price_record)
                db.commit()
                
                return PriceResponse(
                    success=True,
                    price_usd=ripple_data.get("usd", 0),
                    change_24h=ripple_data.get("usd_24h_change", 0),
                    market_cap=ripple_data.get("usd_market_cap", 0),
                    volume_24h=ripple_data.get("usd_24h_vol", 0),
                    timestamp=datetime.utcnow().isoformat()
                )
            else:
                # Try to get last cached price
                last_price = db.query(PriceHistory).order_by(
                    PriceHistory.timestamp.desc()
                ).first()
                
                if last_price:
                    return PriceResponse(
                        success=True,
                        price_usd=last_price.price_usd,
                        change_24h=last_price.change_24h,
                        market_cap=last_price.market_cap,
                        volume_24h=last_price.volume_24h,
                        timestamp=last_price.timestamp.isoformat()
                    )
                else:
                    return PriceResponse(
                        success=False,
                        error="Price service unavailable and no cache available"
                    )
                
    except Exception as e:
        print(f"❌ Price fetch error: {str(e)}")
        
        # Try to get last cached price on error
        try:
            last_price = db.query(PriceHistory).order_by(
                PriceHistory.timestamp.desc()
            ).first()
            
            if last_price:
                return PriceResponse(
                    success=True,
                    price_usd=last_price.price_usd,
                    change_24h=last_price.change_24h,
                    market_cap=last_price.market_cap,
                    volume_24h=last_price.volume_24h,
                    timestamp=last_price.timestamp.isoformat()
                )
        except:
            pass
        
        return PriceResponse(
            success=False,
            error=str(e)
        )

@router.get("/price/history")
async def get_price_history(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get historical XRP prices"""
    try:
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        prices = db.query(PriceHistory).filter(
            PriceHistory.timestamp >= cutoff_time
        ).order_by(
            PriceHistory.timestamp.desc()
        ).limit(100).all()
        
        return {
            "success": True,
            "prices": [
                {
                    "price_usd": p.price_usd,
                    "timestamp": p.timestamp.isoformat()
                }
                for p in prices
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============= Admin/Debug Endpoints (remove in production) =============

if settings.DEBUG:
    @router.get("/debug/users")
    async def list_all_users(db: Session = Depends(get_db)):
        """Debug endpoint to list all users (REMOVE IN PRODUCTION)"""
        users = db.query(User).all()
        return {
            "count": len(users),
            "users": [
                {
                    "id": u.id,
                    "telegram_id": u.telegram_id,
                    "username": u.telegram_username
                }
                for u in users
            ]
        }