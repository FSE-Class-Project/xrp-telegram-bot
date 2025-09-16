#!/usr/bin/env python
"""
XRP Telegram Bot - Development Startup Script
Run both backend API and Telegram bot in development mode
"""

import os
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_banner():
    """Print startup banner"""
    print(
        f"""
{BLUE}================================================
       XRP Telegram Bot - Development
           TestNet Environment
================================================{RESET}
    """
    )


def check_requirements():
    """Check if all requirements are installed with version verification"""
    required_packages = [
        ("fastapi", "0.109.0"),
        ("telegram", "20.3.0"),
        ("xrpl", "2.5.0"),
        ("sqlalchemy", "2.0.25"),
        ("cryptography", "41.0.7"),
        ("httpx", "0.24.1"),
        ("uvicorn", "0.27.0"),
        ("pydantic", "2.5.3"),
    ]

    missing_packages = []
    version_mismatches = []

    for package_name, min_version in required_packages:
        try:
            if package_name == "telegram":
                # Special case for python-telegram-bot package name
                import telegram

                module = telegram
            else:
                module = __import__(package_name)

            # Check version if available
            if hasattr(module, "__version__"):
                current_version = module.__version__
                # Simple version comparison (works for most cases)
                if current_version < min_version:
                    version_mismatches.append(f"{package_name}: {current_version} < {min_version}")

        except ImportError:
            missing_packages.append(package_name)

    if missing_packages:
        print(f"{RED}[ERR] Missing packages: {', '.join(missing_packages)}{RESET}")
        print(f"{YELLOW}Run: pip install -r requirements.txt{RESET}")
        return False

    if version_mismatches:
        print(f"{YELLOW}[WARN] Version mismatches detected:{RESET}")
        for mismatch in version_mismatches:
            print(f"{YELLOW}  - {mismatch}{RESET}")
        print(f"{YELLOW}Consider running: pip install --upgrade -r requirements.txt{RESET}")

    print(f"{GREEN}[OK] All required packages installed{RESET}")
    return True


def check_environment():
    """Check if required environment variables are set"""
    required = ["TELEGRAM_BOT_TOKEN"]
    missing = []

    for var in required:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print(f"{RED}[ERR] Missing environment variables: {', '.join(missing)}{RESET}")
        print(f"{YELLOW}Please check your .env file{RESET}")
        return False

    print(f"{GREEN}[OK] Environment variables configured{RESET}")
    return True


def initialize_database():
    """Initialize the database"""
    try:
        from backend.config import initialize_settings, settings
        from backend.database.connection import init_database, initialize_database_engine

        # Initialize settings first
        initialize_settings()

        print(f"{YELLOW}Initializing database...{RESET}")

        # Initialize database engine and schema
        initialize_database_engine(settings.DATABASE_URL, settings.DEBUG)
        init_database()
        print(f"{GREEN}[OK] Database initialized{RESET}")

        # Ensure encryption key exists
        encryption_key = settings.ensure_encryption_key()
        if encryption_key == settings.ENCRYPTION_KEY and not os.getenv("ENCRYPTION_KEY"):
            print(f"{YELLOW}! Generated new ENCRYPTION_KEY - add this to your .env file!{RESET}")
            print(f"{YELLOW}  ENCRYPTION_KEY={encryption_key[:8]}...{encryption_key[-4:]}{RESET}")
            print(
                f"{GREEN}  Full key saved to logs - check application output for complete key{RESET}"
            )

        return True
    except Exception as e:
        print(f"{RED}[ERR] Database initialization failed: {e}{RESET}")
        return False


def start_backend():
    """Start the FastAPI backend"""
    print(f"\n{BLUE}Starting Backend API...{RESET}")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]

    process = subprocess.Popen(cmd)
    print(f"{GREEN}[OK] Backend API started on http://localhost:8000{RESET}")
    print("  Documentation: http://localhost:8000/docs")

    return process


def cleanup_telegram_instances():
    """Clean up any existing Telegram bot connections"""
    import asyncio

    from telegram import Bot

    async def cleanup():
        try:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                return

            bot = Bot(token=bot_token)
            # Initialize the bot and delete webhook with pending updates
            await bot.initialize()
            try:
                await Bot.delete_webhook(bot, drop_pending_updates=True)
            finally:
                await bot.shutdown()
            print(f"{GREEN}[OK] Cleared existing bot connections{RESET}")
        except Exception as e:
            print(f"{YELLOW}! Warning: Could not clear bot connections: {e}{RESET}")

    try:
        asyncio.run(cleanup())
    except Exception:
        pass  # Ignore cleanup errors


def wait_for_backend(max_attempts=30, delay=1):
    """Wait for backend to be ready with proper health checks"""
    import requests

    print(f"{YELLOW}Waiting for backend to be ready...{RESET}")

    for attempt in range(max_attempts):
        try:
            # Check health endpoint
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print(f"{GREEN}[OK] Backend API is ready (attempt {attempt + 1})${RESET}")
                return True
        except requests.exceptions.RequestException as e:
            if attempt < max_attempts - 1:
                print(
                    f"{YELLOW}Attempt {attempt + 1}: Backend not ready, waiting {delay}s...{RESET}"
                )
                time.sleep(delay)
            else:
                print(f"{RED}[ERR] Backend health check failed: {e}{RESET}")

    return False


def start_bot():
    """Start the Telegram bot"""
    print(f"\n{BLUE}Starting Telegram Bot...{RESET}")

    # Clean up any existing bot connections first
    cleanup_telegram_instances()

    # Wait for backend to be ready with proper health checks
    if not wait_for_backend():
        print(f"{RED}[ERR] Backend is not ready, cannot start bot{RESET}")
        return None

    cmd = [sys.executable, "-m", "bot.main"]
    try:
        process = subprocess.Popen(cmd)
        print(f"{GREEN}[OK] Telegram Bot started{RESET}")

        # Give bot a moment to initialize and check if it's still running
        time.sleep(2)
        if process.poll() is not None:
            print(f"{RED}[ERR] Bot process exited immediately{RESET}")
            return None

        return process
    except Exception as e:
        print(f"{RED}[ERR] Failed to start bot: {e}{RESET}")
        return None


def graceful_shutdown(backend_process, bot_process):
    """Gracefully shutdown all processes"""
    print(f"\n{YELLOW}Shutting down services...{RESET}")

    processes = []
    if bot_process and bot_process.poll() is None:
        processes.append(("Bot", bot_process))
    if backend_process and backend_process.poll() is None:
        processes.append(("Backend", backend_process))

    # Terminate processes gracefully
    for name, process in processes:
        try:
            print(f"{YELLOW}Stopping {name}...{RESET}")
            process.terminate()

            # Wait up to 5 seconds for graceful shutdown
            try:
                process.wait(timeout=5)
                print(f"{GREEN}[OK] {name} stopped gracefully{RESET}")
            except subprocess.TimeoutExpired:
                print(f"{YELLOW}Force killing {name}...{RESET}")
                process.kill()
                process.wait()
                print(f"{GREEN}[OK] {name} force stopped{RESET}")

        except Exception as e:
            print(f"{RED}[ERR] Error stopping {name}: {e}{RESET}")


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

    def signal_handler(_signum, _frame):
        """Handle shutdown signals"""
        graceful_shutdown(backend_process, bot_process)
        sys.exit(0)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start backend
        backend_process = start_backend()
        time.sleep(3)  # Give backend time to start

        # Start bot
        bot_process = start_bot()
        if bot_process is None:
            print(f"{RED}[ERR] Failed to start bot, shutting down backend{RESET}")
            graceful_shutdown(backend_process, None)
            return 1

        print(f"\n{GREEN}==============================================={RESET}")
        print(f"{GREEN}[OK] All services started successfully!{RESET}")
        print(f"\n{BLUE}Available endpoints:{RESET}")
        print("  • API: http://localhost:8000")
        print("  • Docs: http://localhost:8000/docs")
        print("  • Health: http://localhost:8000/api/v1/health")
        print(f"\n{BLUE}Bot Commands:{RESET}")
        print("  • /start - Register and create wallet")
        print("  • /balance - Check XRP balance")
        print("  • /send - Send XRP to another address")
        print("  • /price - View current XRP price")
        print("  • /history - View transaction history")
        print("  • /help - Show all commands")
        print(f"\n{YELLOW}Press Ctrl+C to stop all services{RESET}")
        print(f"{GREEN}==============================================={RESET}\n")

        # Enhanced process monitoring
        try:
            check_interval = 5  # Check every 5 seconds
            while True:
                # Check if processes are still running
                backend_alive = backend_process.poll() is None
                bot_alive = bot_process and bot_process.poll() is None

                if not backend_alive:
                    print(
                        f"{RED}[ERR] Backend process exited unexpectedly (code: {backend_process.poll()}){RESET}"
                    )
                    if bot_process:
                        print(f"{YELLOW}Stopping bot due to backend failure...{RESET}")
                        graceful_shutdown(None, bot_process)
                    return 1

                if bot_process and not bot_alive:
                    print(
                        f"{RED}[ERR] Bot process exited unexpectedly (code: {bot_process.poll()}){RESET}"
                    )
                    print(f"{YELLOW}Bot died but backend is still running{RESET}")
                    print(f"{YELLOW}You can restart just the bot with: python run.py bot{RESET}")
                    graceful_shutdown(backend_process, None)
                    return 1

                # Both processes are healthy
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Received interrupt signal{RESET}")
            graceful_shutdown(backend_process, bot_process)
            return 0

    except Exception as e:
        print(f"{RED}[ERR] Error: {e}{RESET}")
        graceful_shutdown(backend_process, bot_process)
        return 1


def main():
    """Main entry point"""
    # Check for production environment
    if os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production":
        print(f"{RED}[ERR] This development script should not be used in production!{RESET}")
        print(f"{YELLOW}In production, use: python -m backend.main{RESET}")
        return 1

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "backend":
            # Run only backend in development mode
            print(f"{BLUE}Running backend in development mode...{RESET}")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--reload",
                ]
            )
        elif command == "bot":
            # Run only bot in development mode
            print(f"{BLUE}Running bot in development polling mode...{RESET}")
            subprocess.run([sys.executable, "-m", "bot.main"])
        elif command == "test":
            # Run tests
            subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])
        else:
            print(f"Unknown command: {command}")
            print("Usage: python run.py [backend|bot|test]")
            print("  backend - Run only FastAPI backend")
            print("  bot     - Run only Telegram bot (polling)")
            print("  test    - Run test suite")
            print("  (no args) - Run both backend and bot together")
            return 1
    else:
        # Run both in development mode
        return run_development()


if __name__ == "__main__":
    sys.exit(main())
