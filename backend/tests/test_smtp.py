#!/usr/bin/env python3
"""
Quick SMTP connection test
"""
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

print("Testing SMTP Connection...")
print(f"Host: {EMAIL_HOST}")
print(f"Port: {EMAIL_PORT}")
print(f"User: {EMAIL_USER}")
print(f"Password: {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT SET'}")
print(f"Password length: {len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 0}")
print()

try:
    print("Connecting to SMTP server...")
    server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
    print("✓ Connected")
    
    print("Starting TLS...")
    server.starttls()
    print("✓ TLS started")
    
    print(f"Logging in as {EMAIL_USER}...")
    server.login(EMAIL_USER, EMAIL_PASSWORD)
    print("✓ Login successful!")
    
    server.quit()
    print("\n✅ SMTP test passed! Email configuration is working.")
    
except Exception as e:
    print(f"\n❌ SMTP test failed: {e}")
    print("\nTroubleshooting:")
    print("1. Verify 2-Step Verification is enabled")
    print("2. Go to https://myaccount.google.com/apppasswords")
    print("3. Delete the existing ZeroQwait app password")
    print("4. Create a new one and copy it immediately")
    print("5. Update backend/.env with the new password (no spaces)")
    print("6. Restart: docker compose restart backend")
