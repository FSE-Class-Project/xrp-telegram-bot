from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database.connection import get_db

# Create router
router = APIRouter(prefix="/api/v1", tags=["API"])

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "XRP Telegram Bot API"}

# TODO: Add more routes for wallet, transactions, etc.
