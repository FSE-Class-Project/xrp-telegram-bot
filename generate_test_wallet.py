#!/usr/bin/env python
"""Generate a test wallet for XRP TestNet
Creates a new wallet and funds it using the TestNet faucet.
"""

import asyncio
import json

import httpx
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models import AccountInfo
from xrpl.wallet import Wallet

from backend.config import settings

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_banner():
    """Print banner."""
    print(
        f"""
{BLUE}================================================
       XRP TestNet Wallet Generator
================================================{RESET}
    """
    )


def generate_wallet():
    """Generate a new XRP wallet."""
    print(f"{YELLOW}Generating new XRP wallet...{RESET}")

    # Generate a new wallet
    wallet = Wallet.create()

    print(f"{GREEN}[OK] Wallet generated successfully!{RESET}")
    print(f"\n{BLUE}Wallet Details:{RESET}")
    print(f"  Address: {wallet.address}")
    print(f"  Public Key: {wallet.public_key}")
    print(f"  Private Key: {wallet.private_key}")
    print(f"  Seed: {wallet.seed}")

    return wallet


async def fund_wallet(wallet):
    """Fund the wallet using TestNet faucet."""
    print(f"\n{YELLOW}Funding wallet from TestNet faucet...{RESET}")

    try:
        # Use the configured faucet URL
        faucet_url = settings.XRP_FAUCET_URL

        async with httpx.AsyncClient() as client:
            # Request funding from faucet
            # Try different faucet request formats
            response = await client.post(
                faucet_url, json={"destination": wallet.address}, timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                print(f"{GREEN}[OK] Wallet funded successfully!{RESET}")
                print(f"  Amount: {result.get('amount', 'Unknown')} XRP")
                print(f"  Transaction: {result.get('hash', 'Unknown')}")
                return True
            else:
                print(f"{RED}[ERR] Faucet request failed: {response.status_code}{RESET}")
                print(f"Response: {response.text}")
                return False

    except Exception as e:
        print(f"{RED}[ERR] Error funding wallet: {e}{RESET}")
        return False


async def check_balance(wallet):
    """Check the wallet balance."""
    print(f"\n{YELLOW}Checking wallet balance...{RESET}")

    try:
        # Connect to TestNet
        client = AsyncJsonRpcClient(settings.XRP_JSON_RPC_URL)

        # Get account info
        account_info = AccountInfo(account=wallet.address, ledger_index="validated")

        response = await client.request(account_info)

        if response.is_successful():
            # Convert drops to XRP (1 XRP = 1,000,000 drops)
            balance_drops = int(response.result["account_data"]["Balance"])
            balance_xrp = balance_drops / 1_000_000

            print(f"{GREEN}[OK] Balance retrieved successfully!{RESET}")
            print(f"  Balance: {balance_xrp} XRP ({balance_drops} drops)")
            print(f"  Sequence: {response.result['account_data']['Sequence']}")
            print(f"  Account Flags: {response.result['account_data']['Flags']}")

            return balance_xrp
        else:
            print(f"{RED}[ERR] Failed to get balance: {response.result}{RESET}")
            return None

    except Exception as e:
        print(f"{RED}[ERR] Error checking balance: {e}{RESET}")
        return None


def save_wallet_info(wallet, balance):
    """Save wallet information to a file."""
    wallet_data = {
        "network": "testnet",
        "address": wallet.address,
        "public_key": wallet.public_key,
        "private_key": wallet.private_key,
        "seed": wallet.seed,
        "balance_xrp": balance,
        "rpc_url": settings.XRP_JSON_RPC_URL,
        "websocket_url": settings.XRP_WEBSOCKET_URL,
        "faucet_url": settings.XRP_FAUCET_URL,
    }

    filename = f"test_wallet_{wallet.address[:8]}.json"

    with open(filename, "w") as f:
        json.dump(wallet_data, f, indent=2)

    print(f"\n{GREEN}[OK] Wallet information saved to: {filename}{RESET}")


async def main():
    """Execute the main function."""
    print_banner()

    # Generate wallet
    wallet = generate_wallet()

    # Fund wallet
    funded = await fund_wallet(wallet)

    if not funded:
        print(f"\n{YELLOW}WARNING: Wallet created but funding failed.{RESET}")
        print(f"{YELLOW}   You can manually fund it later using:{RESET}")
        print(f"   {settings.XRP_FAUCET_URL}")

        # Still try to check balance
        await asyncio.sleep(2)
    else:
        # Wait for transaction to be processed
        print(f"\n{YELLOW}Waiting for transaction to be processed...{RESET}")
        await asyncio.sleep(5)

    # Check balance
    balance = await check_balance(wallet)

    if balance is not None:
        # Save wallet info
        save_wallet_info(wallet, balance)
    else:
        # Save wallet info without balance
        save_wallet_info(wallet, 0)

    print(f"\n{BLUE}Usage Instructions:{RESET}")
    print(f"1. Use this address to receive XRP: {wallet.address}")
    print("2. Use the seed/private key to send XRP from this wallet")
    print("3. This is TestNet XRP - not real money!")
    print(f"4. You can fund more XRP at: {settings.XRP_FAUCET_URL}")
    print(f"\n{GREEN}Test wallet ready for use!{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
