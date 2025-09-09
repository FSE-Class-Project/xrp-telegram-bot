#!/usr/bin/env python
"""
XRP Telegram Bot - Development Startup Script
Run both backend API and Telegram bot in development mode
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_banner():
    """Print startup banner"""
    print(f"""
{BLUE}╔══════════════════════════════════════════╗
║       XRP Telegram Bot - Development          ║
║           TestNet Environment                 ║
╚══════════════════════════════════════════╝{RESET}
    """)

def check_requirements():
    """Check if all requirements are installed"""
    try:
        import fastapi
        import telegram
        import xrpl
        import sqlalchemy
        import cryptography
        import httpx
        print(f"{GREEN}✓ All required packages installed{RESET}")
        return True
    except ImportError as e:
        print(f"{RED}✗ Missing package: {e.name}{RESET}")
        print(f"{YELLOW}Run: pip install -r requirements.txt{RESET}")
        return False

def check_environment():
    """Check if required environment variables are set"""
    required = ["TELEGRAM_BOT_TOKEN"]
    missing = []
    
    for var in required:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"{RED}✗ Missing environment variables: {', '.join(missing)}{RESET}")
        print(f"{YELLOW}Please check your .env file{RESET}")
        return False
    
    print(f"{GREEN}✓ Environment variables configured{RESET}")
    return True

def initialize_database():
    """Initialize the database"""
    try:
        from backend.database.connection import init_database
        from backend.config import settings
        
        print(f"{YELLOW}Initializing database...{RESET}")
        init_database()
        print(f"{GREEN}✓ Database initialized{RESET}")
        
        # Generate encryption key if needed
        if not settings.ENCRYPTION_KEY:
            key = settings.generate_encryption_key()
            print(f"{YELLOW}⚠ Generated ENCRYPTION_KEY: {key}{RESET}")
            print(f"{YELLOW}  Add this to your .env file!{RESET}")
        
        return True
    except Exception as e:
        print(f"{RED}✗ Database initialization failed: {e}{RESET}")
        return False

def start_backend():
    """Start the FastAPI backend"""
    print(f"\n{BLUE}Starting Backend API...{RESET}")
    
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", 
           "--host", "0.0.0.0", "--port", "8000", "--reload"]
    
    process = subprocess.Popen(cmd)
    print(f"{GREEN}✓ Backend API started on http://localhost:8000{RESET}")
    print(f"  Documentation: http://localhost:8000/docs")
    
    return process

def start_bot():
    """Start the Telegram bot"""
    print(f"\n{BLUE}Starting Telegram Bot...{RESET}")
    
    # Wait for backend to be ready
    import httpx
    import asyncio
    
    async def wait_for_backend():
        for i in range(10):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get("http://localhost:8000/api/v1/health")
                    if response.status_code == 200:
                        return True
            except:
                pass
            await asyncio.sleep(1)
        return False
    
    if asyncio.run(wait_for_backend()):
        print(f"{GREEN}✓ Backend API is ready{RESET}")
    else:
        print(f"{YELLOW}⚠ Backend API may not be ready yet{RESET}")
    
    cmd = [sys.executable, "-m", "bot.main"]
    process = subprocess.Popen(cmd)
    print(f"{GREEN}✓ Telegram Bot started{RESET}")
    
    return process

def run_development():
    """Run both backend and bot in development mode"""
    print_banner()
    
    # Check requirements
    if not check_requirements():
        return 1
    
    # Check environment
    if not check_environment():
        return 1
    
    # Initialize database
    if not initialize_database():
        return 1
    
    # Start services
    backend_process = None
    bot_process = None
    
    try:
        # Start backend
        backend_process = start_backend()
        time.sleep(3)  # Give backend time to start
        
        # Start bot
        bot_process = start_bot()
        
        print(f"\n{GREEN}═══════════════════════════════════════════{RESET}")
        print(f"{GREEN}✓ All services started successfully!{RESET}")
        print(f"\n{BLUE}Available endpoints:{RESET}")
        print(f"  • API: http://localhost:8000")
        print(f"  • Docs: http://localhost:8000/docs")
        print(f"  • Health: http://localhost:8000/api/v1/health")
        print(f"\n{BLUE}Bot Commands:{RESET}")
        print(f"  • /start - Register and create wallet")
        print(f"  • /balance - Check XRP balance")
        print(f"  • /send - Send XRP to another address")
        print(f"  • /price - View current XRP price")
        print(f"  • /history - View transaction history")
        print(f"  • /help - Show all commands")
        print(f"\n{YELLOW}Press Ctrl+C to stop all services{RESET}")
        print(f"{GREEN}═══════════════════════════════════════════{RESET}\n")
        
        # Wait for interrupt
        backend_process.wait()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down services...{RESET}")
        
        # Terminate processes
        if backend_process:
            backend_process.terminate()
            backend_process.wait()
            print(f"{GREEN}✓ Backend stopped{RESET}")
        
        if bot_process:
            bot_process.terminate()
            bot_process.wait()
            print(f"{GREEN}✓ Bot stopped{RESET}")
        
        print(f"{GREEN}✓ All services stopped successfully{RESET}")
        return 0
    
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}")
        return 1

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "backend":
            # Run only backend
            subprocess.run([sys.executable, "-m", "backend.main"])
        elif command == "bot":
            # Run only bot
            subprocess.run([sys.executable, "-m", "bot.main"])
        elif command == "test":
            # Run tests
            subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])
        else:
            print(f"Unknown command: {command}")
            print("Usage: python run.py [backend|bot|test]")
            return 1
    else:
        # Run both in development mode
        return run_development()

if __name__ == "__main__":
    sys.exit(main())