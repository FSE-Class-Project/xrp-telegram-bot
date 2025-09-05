from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field

from ..database.connection import get_db
from ..services.user_service import user_service
from ..services.xrp_service import xrp_service
from ..database.models import User

# Create router
router = APIRouter(prefix="/api/v1", tags=["API"])

# Pydantic models for request/response
class UserRegistration(BaseModel):
    telegram_id: str
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None
    telegram_last_name: Optional[str] = None

class UserResponse(BaseModel):
    user_id: int
    telegram_id: str
    xrp_address: str
    balance: float

class SendTransactionRequest(BaseModel):
    from_telegram_id: str
    to_address: str
    amount: float = Field(gt=0, description="Amount must be positive")
    memo: Optional[str] = None

class TransactionResponse(BaseModel):
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    amount: Optional[float] = None
    fee: Optional[float] = None

class BalanceResponse(BaseModel):
    address: str
    balance: float
    last_updated: Optional[str] = None

# Routes
@router.post("/user/register", response_model=UserResponse)
async def register_user(
    registration: UserRegistration,
    db: Session = Depends(get_db)
):
    """Register a new user and create XRP wallet"""
    try:
        user = await user_service.create_user(
            db=db,
            telegram_id=registration.telegram_id,
            telegram_username=registration.telegram_username,
            telegram_first_name=registration.telegram_first_name,
            telegram_last_name=registration.telegram_last_name
        )
        
        return UserResponse(
            user_id=user.id,
            telegram_id=user.telegram_id,
            xrp_address=user.wallet.xrp_address if user.wallet else "",
            balance=user.wallet.balance if user.wallet else 0.0
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/wallet/balance/{telegram_id}", response_model=BalanceResponse)
async def get_balance(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """Get user's XRP balance"""
    user = user_service.get_user_by_telegram_id(db, telegram_id)
    
    if not user or not user.wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or wallet not found"
        )
    
    # Update balance from blockchain
    balance = await user_service.update_balance(db, user)
    
    return BalanceResponse(
        address=user.wallet.xrp_address,
        balance=balance,
        last_updated=user.wallet.last_balance_update.isoformat() 
            if user.wallet.last_balance_update else None
    )

@router.post("/transaction/send", response_model=TransactionResponse)
async def send_transaction(
    request: SendTransactionRequest,
    db: Session = Depends(get_db)
):
    """Send XRP to another address"""
    # Get sender
    sender = user_service.get_user_by_telegram_id(db, request.from_telegram_id)
    
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender not found"
        )
    
    # Send transaction
    result = await user_service.send_xrp(
        db=db,
        sender=sender,
        recipient_address=request.to_address,
        amount=request.amount,
        memo=request.memo
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Transaction failed")
        )
    
    return TransactionResponse(**result)

@router.get("/transaction/history/{telegram_id}")
async def get_transaction_history(
    telegram_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get user's transaction history"""
    user = user_service.get_user_by_telegram_id(db, telegram_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    history = user_service.get_transaction_history(db, user, limit)
    return {"transactions": history}

@router.get("/price/current")
async def get_current_price():
    """Get current XRP price from CoinGecko"""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
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
                return {
                    "price_usd": data["ripple"]["usd"],
                    "change_24h": data["ripple"].get("usd_24h_change", 0),
                    "market_cap": data["ripple"].get("usd_market_cap", 0),
                    "volume_24h": data["ripple"].get("usd_24h_vol", 0)
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Price service unavailable"
                )
                
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "XRP Telegram Bot API"}