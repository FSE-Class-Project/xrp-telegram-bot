"""
Performance tests:
- Simulate user sign ups
- Simulate peer-to-peer payments
- Generate synthetic users
"""

import asyncio
import random
import time
from datetime import datetime
from typing import Any

import httpx
import pandas as pd
from faker import Faker


class PerformanceTestSuite:
    """Performance testing for XRP Telegram Bot"""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.faker = Faker()
        self.results = {"signups": [], "transactions": [], "balance_checks": []}

    def generate_synthetic_user(self) -> dict[str, Any]:
        """Generate synthetic user data"""
        telegram_id = str(random.randint(100000000, 999999999))
        return {
            "telegram_id": telegram_id,
            "telegram_username": self.faker.user_name(),
            "telegram_first_name": self.faker.first_name(),
            "telegram_last_name": self.faker.last_name(),
        }

    async def signup_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate user signup"""
        start_time = time.time()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(f"{self.api_url}/api/v1/user/register", json=user_data)

                elapsed_time = time.time() - start_time

                return {
                    "success": response.status_code == 200,
                    "user_id": user_data["telegram_id"],
                    "response_time": elapsed_time,
                    "status_code": response.status_code,
                    "data": response.json() if response.status_code == 200 else None,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                return {
                    "success": False,
                    "user_id": user_data["telegram_id"],
                    "response_time": time.time() - start_time,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

    async def send_payment(self, from_id: str, to_address: str, amount: float) -> dict[str, Any]:
        """Simulate P2P payment"""
        start_time = time.time()

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.api_url}/api/v1/transaction/send",
                    json={"from_telegram_id": from_id, "to_address": to_address, "amount": amount},
                )

                elapsed_time = time.time() - start_time

                return {
                    "success": response.status_code == 200,
                    "from_id": from_id,
                    "to_address": to_address,
                    "amount": amount,
                    "response_time": elapsed_time,
                    "status_code": response.status_code,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                return {
                    "success": False,
                    "from_id": from_id,
                    "response_time": time.time() - start_time,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

    async def check_balance(self, telegram_id: str) -> dict[str, Any]:
        """Simulate balance check"""
        start_time = time.time()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.api_url}/api/v1/wallet/balance/{telegram_id}")

                elapsed_time = time.time() - start_time

                return {
                    "success": response.status_code == 200,
                    "user_id": telegram_id,
                    "response_time": elapsed_time,
                    "status_code": response.status_code,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                return {
                    "success": False,
                    "user_id": telegram_id,
                    "response_time": time.time() - start_time,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

    async def test_concurrent_signups(self, num_users: int = 10) -> list[dict[str, Any]]:
        """Test concurrent user signups"""
        print(f"\n🚀 Testing {num_users} concurrent user signups...")

        # Generate synthetic users
        users = [self.generate_synthetic_user() for _ in range(num_users)]

        # Run signups concurrently
        tasks = [self.signup_user(user) for user in users]
        results = await asyncio.gather(*tasks)

        self.results["signups"].extend(results)

        # Analyze results
        successful = sum(1 for r in results if r["success"])
        avg_time = sum(r["response_time"] for r in results) / len(results)
        max_time = max(r["response_time"] for r in results)
        min_time = min(r["response_time"] for r in results)

        print(f"✅ Successful signups: {successful}/{num_users}")
        print(f"⏱️ Average response time: {avg_time:.2f}s")
        print(f"⏱️ Min/Max response time: {min_time:.2f}s / {max_time:.2f}s")

        return results

    async def test_concurrent_payments(
        self, users: list[dict], num_payments: int = 20
    ) -> list[dict[str, Any]]:
        """Test concurrent P2P payments"""
        print(f"\n💸 Testing {num_payments} concurrent P2P payments...")

        if len(users) < 2:
            print("⚠️ Need at least 2 users for P2P payments")
            return []

        # Generate random payments between users
        payments = []
        for _ in range(num_payments):
            from_user = random.choice(users)
            to_user = random.choice([u for u in users if u != from_user])

            if from_user.get("data") and to_user.get("data"):
                payments.append(
                    {
                        "from_id": from_user["data"]["telegram_id"],
                        "to_address": to_user["data"]["xrp_address"],
                        "amount": round(random.uniform(1, 10), 2),
                    }
                )

        if not payments:
            print("⚠️ No valid payment pairs found.")
            return []

        # Run payments concurrently
        tasks = [self.send_payment(p["from_id"], p["to_address"], p["amount"]) for p in payments]
        results = await asyncio.gather(*tasks)

        self.results["transactions"].extend(results)

        # Analyze results
        successful = sum(1 for r in results if r["success"])
        avg_time = sum(r["response_time"] for r in results) / len(results) if results else 0

        print(f"✅ Successful payments: {successful}/{len(results)}")
        print(f"⏱️ Average response time: {avg_time:.2f}s")

        return results

    async def test_load_pattern(self, duration_seconds: int = 60) -> None:
        """Test with realistic load pattern over time"""
        print(f"\n📊 Running load test for {duration_seconds} seconds...")

        start_time = time.time()
        operations_count = 0

        while time.time() - start_time < duration_seconds:
            # Simulate varying load
            load_factor = random.choice([0.5, 1.0, 1.5, 2.0])

            # Random operation
            operation = random.choice(["signup", "balance", "payment"])

            if operation == "signup":
                user_data = self.generate_synthetic_user()
                result = await self.signup_user(user_data)
                self.results["signups"].append(result)
            elif operation == "balance" and self.results["signups"]:
                successful_users = [s for s in self.results["signups"] if s.get("data")]
                if successful_users:
                    user = random.choice(successful_users)
                    result = await self.check_balance(user["data"]["telegram_id"])
                    self.results["balance_checks"].append(result)
            elif operation == "payment" and len(self.results["signups"]) >= 2:
                # Pick two random users for payment
                users_with_data = [s for s in self.results["signups"] if s.get("data")]
                if len(users_with_data) >= 2:
                    from_user = random.choice(users_with_data)
                    to_user = random.choice([u for u in users_with_data if u != from_user])
                    result = await self.send_payment(
                        from_user["data"]["telegram_id"],
                        to_user["data"]["xrp_address"],
                        round(random.uniform(1, 5), 2),
                    )
                    self.results["transactions"].append(result)

            operations_count += 1

            # Variable delay to simulate realistic usage
            await asyncio.sleep(random.uniform(0.5, 2.0) / load_factor)

        print(f"✅ Completed {operations_count} operations in {duration_seconds} seconds.")

    def generate_report(self) -> str:
        """Generate performance test report"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("📊 PERFORMANCE TEST REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().isoformat()}")

        # Signup statistics
        if self.results["signups"]:
            signups = self.results["signups"]
            successful_signups = [s for s in signups if s["success"]]
            failed_signups = [s for s in signups if not s["success"]]

            report.append("\n📝 USER SIGNUPS")
            report.append("-" * 40)
            report.append(f"Total attempts: {len(signups)}")
            report.append(f"Successful: {len(successful_signups)}")
            report.append(f"Failed: {len(failed_signups)}")

            if successful_signups:
                response_times = [s["response_time"] for s in successful_signups]
                report.append(f"Avg response time: {sum(response_times)/len(response_times):.2f}s")
                report.append(f"Min response time: {min(response_times):.2f}s")
                report.append(f"Max response time: {max(response_times):.2f}s")
                report.append(f"95th percentile: {pd.Series(response_times).quantile(0.95):.2f}s")

        # Transaction statistics
        if self.results["transactions"]:
            transactions = self.results["transactions"]
            successful_tx = [t for t in transactions if t["success"]]
            failed_tx = [t for t in transactions if not t["success"]]

            report.append("\n💸 P2P PAYMENTS")
            report.append("-" * 40)
            report.append(f"Total attempts: {len(transactions)}")
            report.append(f"Successful: {len(successful_tx)}")
            report.append(f"Failed: {len(failed_tx)}")

            if successful_tx:
                response_times = [t["response_time"] for t in successful_tx]
                amounts = [t["amount"] for t in successful_tx]
                report.append(f"Avg response time: {sum(response_times)/len(response_times):.2f}s")
                report.append(f"Min response time: {min(response_times):.2f}s")
                report.append(f"Max response time: {max(response_times):.2f}s")
                report.append(f"Total XRP transferred: {sum(amounts):.2f}")
                report.append(f"Avg transaction amount: {sum(amounts)/len(amounts):.2f} XRP")

        # Balance check statistics
        if self.results["balance_checks"]:
            balance_checks = self.results["balance_checks"]
            successful_checks = [b for b in balance_checks if b["success"]]

            report.append("\n💰 BALANCE CHECKS")
            report.append("-" * 40)
            report.append(f"Total checks: {len(balance_checks)}")
            report.append(f"Successful: {len(successful_checks)}")

            if successful_checks:
                response_times = [b["response_time"] for b in successful_checks]
                report.append(f"Avg response time: {sum(response_times)/len(response_times):.2f}s")

        report.append("\n" + "=" * 60)

        return "\n".join(report)

    def save_results(self, filename: str = "performance_results.json") -> None:
        """Save test results to file"""
        import json

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"💾 Results saved to {filename}")


async def main():
    """Run performance tests"""
    # Initialize test suite
    tester = PerformanceTestSuite()

    print("🏁 Starting Performance Tests for XRP Telegram Bot")
    print("=" * 60)

    # Test 1: Concurrent user signups
    signup_results = await tester.test_concurrent_signups(num_users=20)

    # Wait a bit for system to stabilize
    await asyncio.sleep(2)

    # Test 2: Concurrent P2P payments
    successful_signups = [s for s in signup_results if s.get("success") and s.get("data")]
    if successful_signups:
        await tester.test_concurrent_payments(successful_signups, num_payments=30)

    # Test 3: Sustained load test
    await tester.test_load_pattern(duration_seconds=30)

    # Generate and print report
    report = tester.generate_report()
    print(report)

    # Save results
    tester.save_results()


if __name__ == "__main__":
    # Run the performance tests
    asyncio.run(main())
