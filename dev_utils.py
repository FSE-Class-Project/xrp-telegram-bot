#!/usr/bin/env python
"""
Development utilities for XRP Telegram Bot
Useful commands for testing and debugging
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_bot_token():
    """Test if Telegram bot token is valid"""
    import httpx
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return False
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        
        if response.status_code == 200:
            bot_info = response.json()["result"]
            print(f"✅ Bot token valid!")
            print(f"   Bot Name: @{bot_info['username']}")
            print(f"   Bot ID: {bot_info['id']}")
            print(f"   First Name: {bot_info['first_name']}")
            return True
        else:
            print(f"❌ Invalid bot token: {response.status_code}")
            return False

async def test_xrp_connection():
    """Test XRP Ledger connection"""
    from backend.services.xrp_service import xrp_service
    
    print("Testing XRP Ledger connection...")
    
    try:
        # Test connection by getting server info
        from xrpl.clients import JsonRpcClient
        from xrpl.models.requests import ServerInfo
        
        client = JsonRpcClient(xrp_service.json_rpc_url)
        request = ServerInfo()
        response = client.request(request)
        
        if response.is_successful():
            print(f"✅ Connected to XRP Ledger TestNet")
            print(f"   Network: {xrp_service.network}")
            print(f"   URL: {xrp_service.json_rpc_url}")
            return True
        else:
            print(f"❌ Failed to connect to XRP Ledger")
            return False
            
    except Exception as e:
        print(f"❌ XRP connection error: {e}")
        return False

async def create_test_wallet():
    """Create a test XRP wallet"""
    from backend.services.xrp_service import xrp_service
    
    print("Creating test wallet...")
    
    try:
        address, encrypted_secret = xrp_service.create_wallet()
        print(f"✅ Wallet created!")
        print(f"   Address: {address}")
        print(f"   Encrypted Secret: {encrypted_secret[:20]}...")
        
        # Try to fund from faucet
        print("   Requesting TestNet XRP from faucet...")
        funded = await xrp_service.fund_wallet_from_faucet(address)
        
        if funded:
            print(f"   ✅ Wallet funded with TestNet XRP")
            
            # Check balance
            balance = await xrp_service.get_balance(address)
            if balance is not None:
                print(f"   Balance: {balance} XRP")
        else:
            print(f"   ⚠️ Failed to fund wallet (faucet may be rate-limited)")
        
        return address, encrypted_secret
        
    except Exception as e:
        print(f"❌ Error creating wallet: {e}")
        return None, None

async def test_database():
    """Test database connection and query"""
    from backend.config import settings
    from backend.database.connection import check_database_health

    print("Testing database connection...")
    print(f"   Database URL: {settings.DATABASE_URL}")

    if not check_database_health():
        print(f"❌ Database connection failed. See logs for details.")
        return False
    
    print(f"✅ Database connected")

    # Now, try to query the User table to ensure models are correct
    try:
        from backend.database.connection import SessionLocal
        from backend.database.models import User
        
        db = SessionLocal()
        user_count = db.query(User).count()
        db.close()
        
        print(f"   Users in database: {user_count}")
        return True
        
    except Exception as e:
        print(f"   ⚠️ Could not query User table: {e}")
        return False

async def test_api():
    """Test if API is running"""
    import httpx
    
    api_url = os.getenv("API_URL", "http://localhost:8000")
    
    print(f"Testing API at {api_url}...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/api/v1/health", timeout=5.0)
            
            if response.status_code == 200:
                print(f"✅ API is running")
                print(f"   Response: {response.json()}")
                return True
            else:
                print(f"⚠️ API returned status {response.status_code}")
                return False
                
    except httpx.ConnectError:
        print(f"❌ API is not running")
        print(f"   Start it with: python run.py backend")
        return False
    except Exception as e:
        print(f"❌ API error: {e}")
        return False

async def reset_database():
    """Reset database (drop and recreate all tables)"""
    from backend.database.models import Base
    from backend.database.connection import engine
    
    response = input("⚠️  This will DELETE all data. Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled")
        return
    
    print("Resetting database...")
    
    try:
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        print("   Dropped all tables")
        
        # Recreate tables
        Base.metadata.create_all(bind=engine)
        print("   Created all tables")
        
        print("✅ Database reset complete")
        return True
        
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        return False

async def run_all_tests():
    """Run all tests"""
    print("🔍 Running all tests...\n")
    
    results = []
    
    # Test bot token
    print("1. Telegram Bot Token")
    results.append(await test_bot_token())
    print()
    
    # Test database
    print("2. Database Connection")
    results.append(await test_database())
    print()
    
    # Test XRP connection
    print("3. XRP Ledger Connection")
    results.append(await test_xrp_connection())
    print()
    
    # Test API
    print("4. API Server")
    results.append(await test_api())
    print()
    
    # Summary
    print("="*50)
    print("Test Summary:")
    print(f"   ✅ Passed: {sum(results)}/{len(results)}")
    print(f"   ❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 All tests passed! Your environment is ready.")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="XRP Bot Development Utilities")
    parser.add_argument("command", 
                        choices=["test-all", "test-bot", "test-db", "test-xrp", 
                                 "test-api", "create-wallet", "reset-db"],
                        help="Command to run")
    
    args = parser.parse_args()
    
    # Map commands to functions
    commands = {
        "test-all": run_all_tests,
        "test-bot": test_bot_token,
        "test-db": test_database,
        "test-xrp": test_xrp_connection,
        "test-api": test_api,
        "create-wallet": create_test_wallet,
        "reset-db": reset_database,
    }
    
    # Run the selected command
    asyncio.run(commands[args.command]())

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments, run all tests
        asyncio.run(run_all_tests())
    else:
        main()

