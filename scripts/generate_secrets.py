#!/usr/bin/env python3
"""Generate secure random secrets for JWT_SECRET and PASSWORD_PEPPER."""
import secrets

print("JWT_SECRET=" + secrets.token_urlsafe(64))
print("PASSWORD_PEPPER=" + secrets.token_urlsafe(32))
print()
print("Copy these values into your .env file.")
