#!/usr/bin/env python3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test password
test_password = "password123"

# Hash from database
db_hash = "$2b$12$UqDtmktQl8xRA0X3HeXC9uFxZenFvzVVae4H/AxOxQDZZQapBSSDC"

# Test verification
print(f"Testing password: {test_password}")
print(f"Database hash: {db_hash}")
print(f"Verification result: {pwd_context.verify(test_password, db_hash)}")

# Try hashing the same password
new_hash = pwd_context.hash(test_password)
print(f"\nNew hash for same password: {new_hash}")
print(f"New hash matches DB hash: {new_hash == db_hash}")
