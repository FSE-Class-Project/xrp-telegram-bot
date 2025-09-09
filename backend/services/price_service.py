"""Price tracking service"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session

from backend.database.models import PriceHistory

class PriceService:
    async def fetch_and_store_price(self, db: Session) -> PriceHistory:
        """Fetch current price and store in database"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "ripple",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true"
                }
            )
            
            if response.status_code == 200:
                data = response.json()["ripple"]
                
                price_record = PriceHistory(
                    price_usd=data["usd"],
                    change_24h=data.get("usd_24h_change"),
                    market_cap=data.get("usd_market_cap"),
                    volume_24h=data.get("usd_24h_vol"),
                    source="coingecko"
                )
                
                db.add(price_record)
                db.commit()
                
                return price_record
        
        raise Exception("Failed to fetch price")
    
    def get_historical_prices(
        self, 
        db: Session, 
        hours: int = 24,
        limit: int = 100
    ) -> list[PriceHistory]:
        """Get historical prices from database"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return db.query(PriceHistory).filter(
            PriceHistory.timestamp >= since
        ).order_by(
            PriceHistory.timestamp.desc()
        ).limit(limit).all()

price_service = PriceService()