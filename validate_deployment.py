#!/usr/bin/env python3
"""
Deployment validation script for XRP Telegram Bot.
Run this after deploying to Render to ensure everything is working.

Usage:
    python validate_deployment.py --api-url https://your-api.onrender.com --bot-token YOUR_BOT_TOKEN
"""
from __future__ import annotations
import asyncio
import argparse
import sys
from typing import Any
from datetime import datetime
from decimal import Decimal
import json

import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich import print as rprint

console = Console()


class DeploymentValidator:
    """Validate XRP Telegram Bot deployment."""
    
    def __init__(self, api_url: str, bot_token: str | None = None):
        self.api_url = api_url.rstrip('/')
        self.bot_token = bot_token
        self.test_results: list[dict[str, Any]] = []
    
    async def run_all_tests(self) -> bool:
        """Run all validation tests."""
        console.print("\n[bold cyan]🚀 XRP Telegram Bot Deployment Validation[/bold cyan]\n")
        
        tests = [
            ("API Health Check", self.test_api_health),
            ("Database Connection", self.test_database),
            ("XRP Ledger Connection", self.test_xrp_ledger),
            ("User Registration", self.test_user_registration),
            ("Balance Check", self.test_balance_check),
            ("Price API", self.test_price_api),
            ("API Documentation", self.test_api_docs),
        ]
        
        if self.bot_token:
            tests.append(("Telegram Bot", self.test_telegram_bot))
        
        all_passed = True
        
        for test_name, test_func in track(tests, description="Running tests..."):
            try:
                success, message = await test_func()
                self.test_results.append({
                    "test": test_name,
                    "passed": success,
                    "message": message
                })
                
                if success:
                    console.print(f"✅ [green]{test_name}[/green]: {message}")
                else:
                    console.print(f"❌ [red]{test_name}[/red]: {message}")
                    all_passed = False
                    
            except Exception as e:
                console.print(f"❌ [red]{test_name}[/red]: Exception - {str(e)}")
                self.test_results.append({
                    "test": test_name,
                    "passed": False,
                    "message": f"Exception: {str(e)}"
                })
                all_passed = False
        
        self.print_summary()
        return all_passed
    
    async def test_api_health(self) -> tuple[bool, str]:
        """Test API health endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.api_url}/api/v1/health")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "healthy":
                        return True, f"API is healthy (v{data.get('version', 'unknown')})"
                    else:
                        return False, f"API unhealthy: {data}"
                elif response.status_code == 503:
                    data = response.json()
                    issues = []
                    if not data.get("database"):
                        issues.append("database")
                    if not data.get("xrp_ledger"):
                        issues.append("XRP Ledger")
                    return False, f"Service unhealthy - Issues with: {', '.join(issues)}"
                else:
                    return False, f"Unexpected status code: {response.status_code}"
                    
            except httpx.ConnectError:
                return False, f"Cannot connect to API at {self.api_url}"
            except Exception as e:
                return False, str(e)
    
    async def test_database(self) -> tuple[bool, str]:
        """Test database connectivity via API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Try to get a non-existent user to test DB query
                response = await client.get(f"{self.api_url}/api/v1/wallet/balance/999999999")
                
                # 404 is expected and shows DB is working
                if response.status_code == 404:
                    return True, "Database connection working"
                else:
                    return False, f"Unexpected response: {response.status_code}"
                    
            except Exception as e:
                return False, f"Database test failed: {str(e)}"
    
    async def test_xrp_ledger(self) -> tuple[bool, str]:
        """Test XRP Ledger connectivity."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Test by checking current price (requires ledger data)
                response = await client.get(f"{self.api_url}/api/v1/price/current")
                
                if response.status_code == 200:
                    data = response.json()
                    price = data.get("price_usd", 0)
                    return True, f"XRP Ledger connected (Price: ${price:.4f})"
                else:
                    return False, f"XRP Ledger test failed: {response.status_code}"
                    
            except Exception as e:
                return False, f"XRP Ledger test error: {str(e)}"
    
    async def test_user_registration(self) -> tuple[bool, str]:
        """Test user registration endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Generate unique test user
                timestamp = int(datetime.now().timestamp())
                test_user = {
                    "telegram_id": str(900000000 + timestamp % 100000),
                    "telegram_username": f"test_user_{timestamp}",
                    "telegram_first_name": "Test",
                    "telegram_last_name": "User"
                }
                
                response = await client.post(
                    f"{self.api_url}/api/v1/user/register",
                    json=test_user
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    address = data.get("xrp_address", "")
                    if address and address.startswith('r'):
                        return True, f"Registration works - Wallet: {address[:10]}..."
                    else:
                        return False, "Registration succeeded but invalid wallet address"
                else:
                    return False, f"Registration failed: {response.status_code}"
                    
            except Exception as e:
                return False, f"Registration test error: {str(e)}"
    
    async def test_balance_check(self) -> tuple[bool, str]:
        """Test balance check functionality."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # First create a test user
                timestamp = int(datetime.now().timestamp())
                test_id = str(800000000 + timestamp % 100000)
                
                # Register user
                reg_response = await client.post(
                    f"{self.api_url}/api/v1/user/register",
                    json={"telegram_id": test_id}
                )
                
                if reg_response.status_code not in [200, 201]:
                    return False, "Could not create test user for balance check"
                
                # Check balance
                balance_response = await client.get(
                    f"{self.api_url}/api/v1/wallet/balance/{test_id}"
                )
                
                if balance_response.status_code == 200:
                    data = balance_response.json()
                    balance = data.get("balance", 0)
                    return True, f"Balance check works (Balance: {balance} XRP)"
                else:
                    return False, f"Balance check failed: {balance_response.status_code}"
                    
            except Exception as e:
                return False, f"Balance test error: {str(e)}"
    
    async def test_price_api(self) -> tuple[bool, str]:
        """Test price API endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.api_url}/api/v1/price/current")
                
                if response.status_code == 200:
                    data = response.json()
                    price = data.get("price_usd", 0)
                    change = data.get("change_24h", 0)
                    return True, f"Price API works (XRP: ${price:.4f}, 24h: {change:+.2f}%)"
                else:
                    return False, f"Price API failed: {response.status_code}"
                    
            except Exception as e:
                return False, f"Price API error: {str(e)}"
    
    async def test_api_docs(self) -> tuple[bool, str]:
        """Test API documentation availability."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.api_url}/docs")
                
                if response.status_code == 200:
                    return True, "API documentation available at /docs"
                else:
                    return False, f"API docs not accessible: {response.status_code}"
                    
            except Exception as e:
                return False, f"API docs test error: {str(e)}"
    
    async def test_telegram_bot(self) -> tuple[bool, str]:
        """Test Telegram bot connectivity."""
        if not self.bot_token:
            return False, "Bot token not provided"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getMe"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        username = bot_info.get("username", "unknown")
                        return True, f"Bot connected: @{username}"
                    else:
                        return False, f"Bot API error: {data.get('description', 'Unknown')}"
                else:
                    return False, f"Bot API request failed: {response.status_code}"
                    
            except Exception as e:
                return False, f"Bot test error: {str(e)}"
    
    def print_summary(self) -> None:
        """Print test results summary."""
        console.print("\n[bold cyan]📊 Test Summary[/bold cyan]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Test", style="cyan", width=30)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Details", width=50)
        
        passed_count = 0
        for result in self.test_results:
            status = "✅ Pass" if result["passed"] else "❌ Fail"
            style = "green" if result["passed"] else "red"
            table.add_row(
                result["test"],
                f"[{style}]{status}[/{style}]",
                result["message"]
            )
            if result["passed"]:
                passed_count += 1
        
        console.print(table)
        
        total = len(self.test_results)
        percentage = (passed_count / total * 100) if total > 0 else 0
        
        console.print(f"\n[bold]Results: {passed_count}/{total} tests passed ({percentage:.1f}%)[/bold]")
        
        if passed_count == total:
            console.print("\n[bold green]🎉 All tests passed! Deployment is healthy.[/bold green]")
        elif passed_count >= total * 0.7:
            console.print("\n[bold yellow]⚠️  Most tests passed but some issues detected.[/bold yellow]")
        else:
            console.print("\n[bold red]❌ Multiple tests failed. Please check your deployment.[/bold red]")
        
        # Provide specific recommendations
        console.print("\n[bold cyan]📝 Recommendations:[/bold cyan]")
        
        for result in self.test_results:
            if not result["passed"]:
                if "Database" in result["test"]:
                    console.print("• Check DATABASE_URL environment variable")
                    console.print("• Ensure database service is running in Render")
                elif "XRP Ledger" in result["test"]:
                    console.print("• Check XRP TestNet status at https://livenet.xrpl.org")
                    console.print("• Verify XRP_JSON_RPC_URL and XRP_WEBSOCKET_URL")
                elif "Telegram" in result["test"]:
                    console.print("• Verify TELEGRAM_BOT_TOKEN is correct")
                    console.print("• Check worker logs in Render dashboard")
                elif "Health" in result["test"]:
                    console.print("• Check service logs in Render dashboard")
                    console.print("• Ensure all environment variables are set")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate XRP Telegram Bot deployment"
    )
    parser.add_argument(
        "--api-url",
        required=True,
        help="API URL (e.g., https://xrp-bot-api.onrender.com)"
    )
    parser.add_argument(
        "--bot-token",
        help="Telegram bot token (optional)"
    )
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(args.api_url, args.bot_token)
    
    try:
        success = await validator.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Validation interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Validation failed with error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    # Check if rich is installed
    try:
        import rich
    except ImportError:
        print("Please install 'rich' library: pip install rich")
        sys.exit(1)
    
    asyncio.run(main())