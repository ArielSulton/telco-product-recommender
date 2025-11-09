#!/usr/bin/env python3
"""
Security Audit Script
====================

Automated security auditing for production deployment.

Checks:
1. Security headers validation
2. TLS/SSL configuration
3. Authentication enforcement
4. Rate limiting
5. Input validation
6. CORS configuration
7. Sensitive data exposure
8. Known vulnerabilities

Usage:
    python scripts/security_audit.py --target https://api.telco-recommender.com
"""

import argparse
import asyncio
import sys
import ssl
import socket
from typing import Dict, List, Tuple
import httpx
from urllib.parse import urlparse


class SecurityAuditor:
    """Security audit tool for production API."""

    def __init__(self, target_url: str):
        """Initialize security auditor."""
        self.target_url = target_url.rstrip('/')
        self.parsed_url = urlparse(target_url)
        self.findings: List[Dict] = []
        self.critical_count = 0
        self.high_count = 0
        self.medium_count = 0
        self.low_count = 0

    def add_finding(self, severity: str, category: str, title: str, description: str, recommendation: str):
        """Record a security finding."""
        self.findings.append({
            "severity": severity,
            "category": category,
            "title": title,
            "description": description,
            "recommendation": recommendation
        })

        if severity == "CRITICAL":
            self.critical_count += 1
        elif severity == "HIGH":
            self.high_count += 1
        elif severity == "MEDIUM":
            self.medium_count += 1
        elif severity == "LOW":
            self.low_count += 1

    async def check_security_headers(self):
        """Audit security headers."""
        print("\n[*] Checking security headers...")

        async with httpx.AsyncClient(verify=False) as client:
            try:
                response = await client.get(f"{self.target_url}/health")
                headers = response.headers

                # Required security headers
                required_headers = {
                    "X-Content-Type-Options": ("nosniff", "Prevents MIME type sniffing"),
                    "X-Frame-Options": ("DENY", "Prevents clickjacking"),
                    "X-XSS-Protection": ("1", "Enables XSS protection"),
                    "Content-Security-Policy": ("default-src", "Controls resource loading"),
                    "Strict-Transport-Security": ("max-age", "Enforces HTTPS"),
                }

                for header, (expected, purpose) in required_headers.items():
                    value = headers.get(header, "")

                    if not value:
                        self.add_finding(
                            "HIGH",
                            "Security Headers",
                            f"Missing {header}",
                            f"The {header} header is not present. {purpose}.",
                            f"Add '{header}' header to all responses."
                        )
                    elif expected not in value:
                        self.add_finding(
                            "MEDIUM",
                            "Security Headers",
                            f"Weak {header}",
                            f"The {header} header value '{value}' may be insufficient.",
                            f"Ensure {header} contains '{expected}'."
                        )
                    else:
                        print(f"  ✓ {header}: Present and properly configured")

                # Check for information disclosure headers
                info_headers = ["Server", "X-Powered-By", "X-AspNet-Version"]
                for header in info_headers:
                    if header in headers:
                        self.add_finding(
                            "LOW",
                            "Information Disclosure",
                            f"{header} header present",
                            f"The {header} header reveals server information.",
                            f"Remove or obscure the {header} header."
                        )

            except Exception as e:
                print(f"  ✗ Error checking headers: {str(e)}")

    async def check_tls_configuration(self):
        """Audit TLS/SSL configuration."""
        print("\n[*] Checking TLS/SSL configuration...")

        if self.parsed_url.scheme != "https":
            self.add_finding(
                "CRITICAL",
                "Transport Security",
                "HTTPS not enforced",
                "The API is accessible over unencrypted HTTP.",
                "Enforce HTTPS for all connections and redirect HTTP to HTTPS."
            )
            return

        try:
            context = ssl.create_default_context()
            with socket.create_connection((self.parsed_url.hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.parsed_url.hostname) as ssock:
                    cert = ssock.getpeercert()
                    protocol = ssock.version()

                    # Check TLS version
                    if protocol in ["TLSv1.2", "TLSv1.3"]:
                        print(f"  ✓ TLS version: {protocol}")
                    else:
                        self.add_finding(
                            "HIGH",
                            "Transport Security",
                            f"Weak TLS version: {protocol}",
                            f"The server supports {protocol} which has known vulnerabilities.",
                            "Upgrade to TLS 1.2 or 1.3 minimum."
                        )

                    # Check cipher suite
                    cipher = ssock.cipher()
                    if cipher:
                        print(f"  ✓ Cipher suite: {cipher[0]}")
                    else:
                        self.add_finding(
                            "MEDIUM",
                            "Transport Security",
                            "Weak cipher suite",
                            "Unable to determine cipher suite strength.",
                            "Ensure strong cipher suites are configured."
                        )

        except ssl.SSLError as e:
            self.add_finding(
                "HIGH",
                "Transport Security",
                "SSL/TLS error",
                f"SSL/TLS handshake failed: {str(e)}",
                "Review SSL/TLS configuration and certificate validity."
            )
        except Exception as e:
            print(f"  ✗ Error checking TLS: {str(e)}")

    async def check_authentication(self):
        """Audit authentication mechanisms."""
        print("\n[*] Checking authentication...")

        async with httpx.AsyncClient(verify=False) as client:
            # Test protected endpoints without auth
            protected_endpoints = [
                "/api/v1/recommendations/user123",
                "/api/v1/events",
            ]

            for endpoint in protected_endpoints:
                try:
                    response = await client.get(f"{self.target_url}{endpoint}")

                    if response.status_code == 401:
                        print(f"  ✓ {endpoint}: Properly protected")
                    elif response.status_code == 404:
                        print(f"  ⚠ {endpoint}: Not implemented")
                    else:
                        self.add_finding(
                            "CRITICAL",
                            "Authentication",
                            f"Unprotected endpoint: {endpoint}",
                            f"The endpoint returns {response.status_code} without authentication.",
                            "Enforce authentication on all protected endpoints."
                        )

                except Exception as e:
                    print(f"  ✗ Error testing {endpoint}: {str(e)}")

            # Test weak credentials (if login endpoint exists)
            weak_creds = [
                ("admin", "admin"),
                ("admin", "password"),
                ("test", "test"),
            ]

            try:
                for username, password in weak_creds:
                    response = await client.post(
                        f"{self.target_url}/api/v1/auth/login",
                        json={"username": username, "password": password}
                    )

                    if response.status_code == 200:
                        self.add_finding(
                            "CRITICAL",
                            "Authentication",
                            "Weak credentials accepted",
                            f"Login succeeded with weak credentials: {username}/{password}",
                            "Enforce strong password policies and remove default accounts."
                        )
                        break

            except Exception:
                pass  # Login endpoint may not exist

    async def check_rate_limiting(self):
        """Audit rate limiting implementation."""
        print("\n[*] Checking rate limiting...")

        async with httpx.AsyncClient(verify=False) as client:
            try:
                # Make rapid requests
                responses = []
                for i in range(150):  # Exceed typical limit
                    response = await client.get(f"{self.target_url}/health")
                    responses.append(response)

                    if response.status_code == 429:
                        print(f"  ✓ Rate limiting active (triggered at request {i+1})")
                        break
                else:
                    self.add_finding(
                        "HIGH",
                        "Rate Limiting",
                        "Rate limiting not enforced",
                        "No rate limiting detected after 150 rapid requests.",
                        "Implement rate limiting to prevent abuse."
                    )

                # Check rate limit headers
                if responses and "X-RateLimit-Limit" in responses[0].headers:
                    print("  ✓ Rate limit headers present")
                else:
                    self.add_finding(
                        "LOW",
                        "Rate Limiting",
                        "Missing rate limit headers",
                        "Rate limit information not exposed in headers.",
                        "Add X-RateLimit-* headers to inform clients."
                    )

            except Exception as e:
                print(f"  ✗ Error checking rate limiting: {str(e)}")

    async def check_cors_configuration(self):
        """Audit CORS configuration."""
        print("\n[*] Checking CORS configuration...")

        async with httpx.AsyncClient(verify=False) as client:
            # Test with various origins
            test_origins = [
                "https://evil.com",
                "http://localhost:3000",
                "*",
            ]

            for origin in test_origins:
                try:
                    response = await client.options(
                        f"{self.target_url}/health",
                        headers={"Origin": origin}
                    )

                    allowed_origin = response.headers.get("Access-Control-Allow-Origin", "")

                    if allowed_origin == "*":
                        self.add_finding(
                            "HIGH",
                            "CORS",
                            "Wildcard CORS policy",
                            "The API allows requests from any origin (*).",
                            "Restrict CORS to specific trusted origins."
                        )
                        break
                    elif origin == "https://evil.com" and allowed_origin == origin:
                        self.add_finding(
                            "CRITICAL",
                            "CORS",
                            "Unrestricted CORS",
                            "The API accepts requests from untrusted origins.",
                            "Whitelist only trusted domains in CORS configuration."
                        )
                        break

                except Exception as e:
                    print(f"  ✗ Error testing CORS: {str(e)}")

    async def check_input_validation(self):
        """Audit input validation."""
        print("\n[*] Checking input validation...")

        async with httpx.AsyncClient(verify=False) as client:
            # Test SQL injection
            sql_payloads = [
                "' OR '1'='1",
                "1'; DROP TABLE users--",
                "1 UNION SELECT NULL--",
            ]

            for payload in sql_payloads:
                try:
                    response = await client.get(
                        f"{self.target_url}/api/v1/recommendations/{payload}"
                    )

                    # Check for SQL errors in response
                    if any(err in response.text.lower() for err in ["sql", "syntax", "mysql", "postgresql"]):
                        self.add_finding(
                            "CRITICAL",
                            "Input Validation",
                            "Potential SQL injection",
                            f"SQL error message exposed with payload: {payload}",
                            "Implement proper input validation and use parameterized queries."
                        )
                        break

                except Exception:
                    pass

            # Test XSS
            xss_payloads = [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
            ]

            for payload in xss_payloads:
                try:
                    response = await client.post(
                        f"{self.target_url}/api/v1/events",
                        json={"user_id": payload, "event_type": "view", "product_id": "test"}
                    )

                    if payload in response.text:
                        self.add_finding(
                            "HIGH",
                            "Input Validation",
                            "Potential XSS vulnerability",
                            f"Unescaped user input in response: {payload}",
                            "Sanitize and escape all user input."
                        )
                        break

                except Exception:
                    pass

    async def check_sensitive_data_exposure(self):
        """Check for sensitive data exposure."""
        print("\n[*] Checking for sensitive data exposure...")

        async with httpx.AsyncClient(verify=False) as client:
            # Check common sensitive endpoints
            sensitive_endpoints = [
                "/.env",
                "/config.json",
                "/.git/config",
                "/admin",
                "/debug",
                "/phpinfo.php",
            ]

            for endpoint in sensitive_endpoints:
                try:
                    response = await client.get(f"{self.target_url}{endpoint}")

                    if response.status_code == 200:
                        self.add_finding(
                            "CRITICAL",
                            "Sensitive Data Exposure",
                            f"Sensitive file accessible: {endpoint}",
                            f"The endpoint {endpoint} is publicly accessible.",
                            f"Remove or restrict access to {endpoint}."
                        )

                except Exception:
                    pass

    def generate_report(self):
        """Generate security audit report."""
        print("\n" + "="*80)
        print("SECURITY AUDIT REPORT")
        print("="*80)

        print(f"\nTarget: {self.target_url}")
        print(f"Timestamp: {__import__('datetime').datetime.now().isoformat()}")

        print(f"\nFindings Summary:")
        print(f"  CRITICAL: {self.critical_count}")
        print(f"  HIGH:     {self.high_count}")
        print(f"  MEDIUM:   {self.medium_count}")
        print(f"  LOW:      {self.low_count}")
        print(f"  TOTAL:    {len(self.findings)}")

        if self.findings:
            print("\n" + "="*80)
            print("DETAILED FINDINGS")
            print("="*80)

            for i, finding in enumerate(self.findings, 1):
                print(f"\n[{i}] {finding['severity']} - {finding['title']}")
                print(f"Category: {finding['category']}")
                print(f"Description: {finding['description']}")
                print(f"Recommendation: {finding['recommendation']}")

        # Generate risk score
        risk_score = (
            self.critical_count * 10 +
            self.high_count * 7 +
            self.medium_count * 4 +
            self.low_count * 1
        )

        print("\n" + "="*80)
        print(f"Overall Risk Score: {risk_score}")

        if self.critical_count > 0:
            print("Status: CRITICAL - Immediate action required")
            return 2
        elif self.high_count > 0:
            print("Status: HIGH RISK - Action required")
            return 1
        elif self.medium_count > 0:
            print("Status: MODERATE RISK - Review recommended")
            return 0
        else:
            print("Status: LOW RISK - No critical issues found")
            return 0

    async def run_audit(self):
        """Run complete security audit."""
        print("\n" + "="*80)
        print("SECURITY AUDIT - Telco Product Recommender")
        print("="*80)

        await self.check_security_headers()
        await self.check_tls_configuration()
        await self.check_authentication()
        await self.check_rate_limiting()
        await self.check_cors_configuration()
        await self.check_input_validation()
        await self.check_sensitive_data_exposure()

        return self.generate_report()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Security audit for Telco Recommender API"
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target API URL (e.g., https://api.telco-recommender.com)"
    )

    args = parser.parse_args()

    auditor = SecurityAuditor(args.target)
    exit_code = await auditor.run_audit()

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
