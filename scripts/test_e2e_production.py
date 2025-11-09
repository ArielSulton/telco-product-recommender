#!/usr/bin/env python3
"""
End-to-End Production Test Script
==================================

Comprehensive E2E testing for production deployment validation.

Tests:
1. Service health checks
2. Authentication flow
3. Recommendation API
4. Event tracking
5. Performance benchmarks
6. Security headers
7. Rate limiting

Usage:
    python scripts/test_e2e_production.py --base-url https://api.telco-recommender.com
"""

import argparse
import asyncio
import sys
import time
from typing import Dict, List, Tuple
import httpx
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


class E2EProductionTest:
    """End-to-end production test suite."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize test suite.

        Args:
            base_url: Base API URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.results: List[Tuple[str, bool, str]] = []
        self.token: str = ""

    def log(self, message: str, color: str = Colors.BLUE):
        """Print colored log message."""
        print(f"{color}{message}{Colors.END}")

    def success(self, test_name: str, message: str = ""):
        """Record successful test."""
        self.results.append((test_name, True, message))
        self.log(f"✓ {test_name}: PASS {message}", Colors.GREEN)

    def failure(self, test_name: str, error: str):
        """Record failed test."""
        self.results.append((test_name, False, error))
        self.log(f"✗ {test_name}: FAIL - {error}", Colors.RED)

    async def test_health_checks(self):
        """Test all health check endpoints."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Basic health check
            try:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "healthy":
                        self.success("Health Check", f"Version: {data.get('version')}")
                    else:
                        self.failure("Health Check", "Status not healthy")
                else:
                    self.failure("Health Check", f"Status code: {response.status_code}")
            except Exception as e:
                self.failure("Health Check", str(e))

            # Readiness check
            try:
                response = await client.get(f"{self.base_url}/health/ready")
                if response.status_code == 200:
                    data = response.json()
                    checks = data.get("checks", {})
                    all_healthy = all(v == "healthy" for v in checks.values())
                    if all_healthy:
                        self.success("Readiness Check", f"All services healthy")
                    else:
                        unhealthy = [k for k, v in checks.items() if v != "healthy"]
                        self.failure("Readiness Check", f"Unhealthy: {unhealthy}")
                else:
                    self.failure("Readiness Check", f"Status code: {response.status_code}")
            except Exception as e:
                self.failure("Readiness Check", str(e))

            # Liveness check
            try:
                response = await client.get(f"{self.base_url}/health/live")
                if response.status_code == 200 and response.json().get("status") == "alive":
                    self.success("Liveness Check")
                else:
                    self.failure("Liveness Check", "Not alive")
            except Exception as e:
                self.failure("Liveness Check", str(e))

    async def test_security_headers(self):
        """Test security headers are present."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                headers = response.headers

                required_headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "X-XSS-Protection": "1; mode=block",
                    "Content-Security-Policy": "default-src",
                }

                missing = []
                for header, expected in required_headers.items():
                    value = headers.get(header, "")
                    if expected not in value:
                        missing.append(header)

                if not missing:
                    self.success("Security Headers", "All required headers present")
                else:
                    self.failure("Security Headers", f"Missing: {missing}")

            except Exception as e:
                self.failure("Security Headers", str(e))

    async def test_cors_configuration(self):
        """Test CORS configuration."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.options(
                    f"{self.base_url}/health",
                    headers={"Origin": "https://app.telco-recommender.com"}
                )

                if "Access-Control-Allow-Origin" in response.headers:
                    self.success("CORS Configuration", "CORS headers present")
                else:
                    self.failure("CORS Configuration", "CORS headers missing")

            except Exception as e:
                self.failure("CORS Configuration", str(e))

    async def test_rate_limiting(self):
        """Test rate limiting is enforced."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Make multiple rapid requests
                responses = []
                for _ in range(10):
                    response = await client.get(f"{self.base_url}/health")
                    responses.append(response)

                # Check for rate limit headers
                first_response = responses[0]
                if "X-RateLimit-Limit" in first_response.headers:
                    limit = first_response.headers["X-RateLimit-Limit"]
                    remaining = first_response.headers.get("X-RateLimit-Remaining", "N/A")
                    self.success("Rate Limiting", f"Limit: {limit}, Remaining: {remaining}")
                else:
                    self.failure("Rate Limiting", "Rate limit headers not found")

            except Exception as e:
                self.failure("Rate Limiting", str(e))

    async def test_authentication_flow(self):
        """Test JWT authentication."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test without authentication (should fail)
            try:
                response = await client.get(f"{self.base_url}/api/v1/recommendations/user123")
                if response.status_code == 401:
                    self.success("Auth Protection", "Endpoints properly protected")
                else:
                    self.failure("Auth Protection", f"Expected 401, got {response.status_code}")
            except Exception as e:
                self.failure("Auth Protection", str(e))

            # Test login (if endpoint exists)
            # Note: Adjust based on your actual auth implementation
            try:
                login_data = {
                    "username": "test@example.com",
                    "password": "test_password"
                }
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json=login_data
                )

                if response.status_code == 200:
                    data = response.json()
                    if "access_token" in data:
                        self.token = data["access_token"]
                        self.success("Authentication", "Token obtained")
                    else:
                        self.failure("Authentication", "No access token in response")
                elif response.status_code == 404:
                    self.log("⚠ Authentication endpoint not implemented yet", Colors.YELLOW)
                else:
                    self.failure("Authentication", f"Status: {response.status_code}")

            except Exception as e:
                self.log(f"⚠ Authentication test skipped: {str(e)}", Colors.YELLOW)

    async def test_recommendation_api(self):
        """Test recommendation API endpoints."""
        if not self.token:
            self.log("⚠ Skipping recommendation tests (no auth token)", Colors.YELLOW)
            return

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Authorization": f"Bearer {self.token}"}

            # Test GET recommendations
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/recommendations/user123",
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    if "recommendations" in data:
                        count = len(data["recommendations"])
                        self.success("GET Recommendations", f"Returned {count} items")
                    else:
                        self.failure("GET Recommendations", "No recommendations field")
                elif response.status_code == 404:
                    self.log("⚠ Recommendations endpoint not fully implemented", Colors.YELLOW)
                else:
                    self.failure("GET Recommendations", f"Status: {response.status_code}")

            except Exception as e:
                self.failure("GET Recommendations", str(e))

            # Test POST recommendations
            try:
                request_data = {
                    "user_id": "user123",
                    "n_recommendations": 5
                }
                response = await client.post(
                    f"{self.base_url}/api/v1/recommendations",
                    json=request_data,
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    if "recommendations" in data:
                        self.success("POST Recommendations", "Request successful")
                    else:
                        self.failure("POST Recommendations", "Invalid response format")
                elif response.status_code == 404:
                    self.log("⚠ POST recommendations not fully implemented", Colors.YELLOW)
                else:
                    self.failure("POST Recommendations", f"Status: {response.status_code}")

            except Exception as e:
                self.failure("POST Recommendations", str(e))

    async def test_event_tracking(self):
        """Test event tracking API."""
        if not self.token:
            self.log("⚠ Skipping event tests (no auth token)", Colors.YELLOW)
            return

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Authorization": f"Bearer {self.token}"}

            # Test single event
            try:
                event_data = {
                    "user_id": "user123",
                    "event_type": "view",
                    "product_id": "prod456",
                    "timestamp": datetime.utcnow().isoformat()
                }
                response = await client.post(
                    f"{self.base_url}/api/v1/events",
                    json=event_data,
                    headers=headers
                )

                if response.status_code == 200:
                    self.success("Event Tracking", "Event recorded")
                elif response.status_code == 404:
                    self.log("⚠ Event tracking not fully implemented", Colors.YELLOW)
                else:
                    self.failure("Event Tracking", f"Status: {response.status_code}")

            except Exception as e:
                self.failure("Event Tracking", str(e))

    async def test_performance(self):
        """Test API performance benchmarks."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test response times
            try:
                times = []
                for _ in range(10):
                    start = time.time()
                    response = await client.get(f"{self.base_url}/health")
                    elapsed = (time.time() - start) * 1000  # Convert to ms
                    times.append(elapsed)

                avg_time = sum(times) / len(times)
                p95_time = sorted(times)[int(len(times) * 0.95)]

                if avg_time < 200:  # Target: < 200ms
                    self.success("Performance", f"Avg: {avg_time:.2f}ms, P95: {p95_time:.2f}ms")
                else:
                    self.failure("Performance", f"Avg: {avg_time:.2f}ms exceeds 200ms target")

            except Exception as e:
                self.failure("Performance", str(e))

    async def test_error_handling(self):
        """Test error handling and response format."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test 404 error
            try:
                response = await client.get(f"{self.base_url}/api/v1/nonexistent")
                if response.status_code == 404:
                    data = response.json()
                    if "error" in data and "request_id" in data["error"]:
                        self.success("Error Handling", "Proper error format")
                    else:
                        self.failure("Error Handling", "Invalid error format")
                else:
                    self.failure("Error Handling", f"Expected 404, got {response.status_code}")

            except Exception as e:
                self.failure("Error Handling", str(e))

    def print_summary(self):
        """Print test summary."""
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}Test Summary{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

        passed = sum(1 for _, success, _ in self.results if success)
        failed = sum(1 for _, success, _ in self.results if not success)
        total = len(self.results)

        print(f"Total Tests: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {failed}{Colors.END}")

        if failed > 0:
            print(f"\n{Colors.BOLD}Failed Tests:{Colors.END}")
            for name, success, error in self.results:
                if not success:
                    print(f"{Colors.RED}  - {name}: {error}{Colors.END}")

        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.END}")

        return failed == 0

    async def run_all_tests(self):
        """Run all test suites."""
        self.log(f"\n{Colors.BOLD}Starting E2E Production Tests{Colors.END}")
        self.log(f"Base URL: {self.base_url}\n")

        # Run tests in sequence
        await self.test_health_checks()
        await self.test_security_headers()
        await self.test_cors_configuration()
        await self.test_rate_limiting()
        await self.test_authentication_flow()
        await self.test_recommendation_api()
        await self.test_event_tracking()
        await self.test_performance()
        await self.test_error_handling()

        # Print summary
        success = self.print_summary()

        return 0 if success else 1


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run E2E production tests for Telco Recommender API"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Run tests
    tester = E2EProductionTest(args.base_url, args.timeout)
    exit_code = await tester.run_all_tests()

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
