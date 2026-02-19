"""
Salesforce Configuration and Client Management
Handles authentication, DNS configuration, and Salesforce client initialization
"""
import time
import sys
import socket
import dns.resolver
import jwt
import requests
from simple_salesforce import Salesforce
from typing import Optional
import os

# -------------------------------------------------
# DNS Fix: Use Google DNS
# -------------------------------------------------
_dns_resolver = dns.resolver.Resolver()
_dns_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
_dns_cache = {}

def _resolve_dns(hostname):
    if hostname not in _dns_cache:
        try:
            _dns_cache[hostname] = str(_dns_resolver.resolve(hostname, 'A')[0])
            print(f"[DNS] {hostname} -> {_dns_cache[hostname]}", file=sys.stderr)
        except Exception as e:
            print(f"[DNS ERROR] {hostname}: {e}", file=sys.stderr)
            return None
    return _dns_cache[hostname]

_original_getaddrinfo = socket.getaddrinfo

def _patched_getaddrinfo(host, port, *args, **kwargs):
    if 'salesforce.com' in str(host):
        ip = _resolve_dns(host)
        if ip:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
    return _original_getaddrinfo(host, port, *args, **kwargs)

socket.getaddrinfo = _patched_getaddrinfo

# -------------------------------------------------
# Salesforce Configuration
# -------------------------------------------------
SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
SF_USERNAME = os.getenv("SF_USERNAME")
SF_LOGIN_URL = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")
SF_PRIVATE_KEY_RAW = os.getenv("SF_PRIVATE_KEY")

if not SF_CLIENT_ID:
    raise ValueError("SF_CLIENT_ID environment variable is required")
if not SF_USERNAME:
    raise ValueError("SF_USERNAME environment variable is required")
if not SF_PRIVATE_KEY_RAW:
    raise ValueError("SF_PRIVATE_KEY environment variable is required")

# Debug: Log raw key info (without exposing full key)
print(f"[SF DEBUG] Raw private key length: {len(SF_PRIVATE_KEY_RAW)}", file=sys.stderr)
print(f"[SF DEBUG] Raw key starts with: {SF_PRIVATE_KEY_RAW[:50]}", file=sys.stderr)
has_literal_newline = '\\n' in SF_PRIVATE_KEY_RAW
has_actual_newline = '\n' in SF_PRIVATE_KEY_RAW
print(f"[SF DEBUG] Raw key contains '\\n': {'Yes' if has_literal_newline else 'No'}", file=sys.stderr)
print(f"[SF DEBUG] Raw key contains actual newline: {'Yes' if has_actual_newline else 'No'}", file=sys.stderr)

# Fix private key formatting - Azure may strip newlines or store \n as literal
# Try multiple methods to restore proper PEM format
SF_PRIVATE_KEY = SF_PRIVATE_KEY_RAW

# Method 1: Replace literal \n (backslash-n) with actual newlines
if "\\n" in SF_PRIVATE_KEY:
    print("[SF] Converting literal \\n to actual newlines", file=sys.stderr)
    SF_PRIVATE_KEY = SF_PRIVATE_KEY.replace("\\n", "\n")

# Method 2: If still no newlines, try to format it
if "\n" not in SF_PRIVATE_KEY:
    print("[SF] No newlines found, attempting to format key", file=sys.stderr)
    # Check if it has BEGIN/END markers
    if "-----BEGIN PRIVATE KEY-----" in SF_PRIVATE_KEY and "-----END PRIVATE KEY-----" in SF_PRIVATE_KEY:
        # Extract the key content (everything between BEGIN and END)
        begin_marker = "-----BEGIN PRIVATE KEY-----"
        end_marker = "-----END PRIVATE KEY-----"
        
        # Find positions
        begin_pos = SF_PRIVATE_KEY.find(begin_marker)
        end_pos = SF_PRIVATE_KEY.find(end_marker)
        
        if begin_pos != -1 and end_pos != -1:
            # Extract key content
            key_start = begin_pos + len(begin_marker)
            key_content = SF_PRIVATE_KEY[key_start:end_pos].strip()
            
            # Remove any remaining \n or spaces, then format properly
            key_content = key_content.replace("\\n", "").replace(" ", "").replace("\t", "")
            
            # Reconstruct with proper newlines
            SF_PRIVATE_KEY = f"{begin_marker}\n{key_content}\n{end_marker}"
            print("[SF] Reformatted private key with newlines", file=sys.stderr)

# Validate key format
if "-----BEGIN PRIVATE KEY-----" not in SF_PRIVATE_KEY:
    raise ValueError("Private key missing BEGIN marker")
if "-----END PRIVATE KEY-----" not in SF_PRIVATE_KEY:
    raise ValueError("Private key missing END marker")
if "\n" not in SF_PRIVATE_KEY:
    print("[WARNING] Private key still has no newlines after processing", file=sys.stderr)

# Final validation and debug
print(f"[SF DEBUG] Final private key length: {len(SF_PRIVATE_KEY)}", file=sys.stderr)
has_final_newlines = '\n' in SF_PRIVATE_KEY
print(f"[SF DEBUG] Final key has newlines: {'Yes' if has_final_newlines else 'No'}", file=sys.stderr)
if has_final_newlines:
    key_lines = SF_PRIVATE_KEY.split('\n')[:3]
    print(f"[SF DEBUG] First 3 lines: {key_lines}", file=sys.stderr)

# -------------------------------------------------
# Salesforce Client
# -------------------------------------------------
_sf_client: Optional[Salesforce] = None
_auth_time: Optional[float] = None

def get_salesforce() -> Salesforce:
    """Get or create Salesforce client"""
    global _sf_client, _auth_time
    
    if _sf_client and _auth_time and (time.time() - _auth_time) > 3600:
        print("[SF] Token expired, re-authenticating...", file=sys.stderr)
        _sf_client = None
    
    if _sf_client is None:
        print("[SF] Authenticating with JWT...", file=sys.stderr)
        t = time.time()
        
        try:
            # Validate private key format
            if not SF_PRIVATE_KEY or len(SF_PRIVATE_KEY) < 100:
                raise ValueError("Private key appears to be invalid or too short")
            
            if "-----BEGIN" not in SF_PRIVATE_KEY or "-----END" not in SF_PRIVATE_KEY:
                raise ValueError("Private key missing PEM markers (BEGIN/END)")
            
            payload = {
                "iss": SF_CLIENT_ID,
                "sub": SF_USERNAME,
                "aud": SF_LOGIN_URL,
                "exp": int(time.time()) + 300,
            }
            
            print(f"[SF] Private key length: {len(SF_PRIVATE_KEY)}", file=sys.stderr)
            print(f"[SF] Private key starts with: {SF_PRIVATE_KEY[:50]}...", file=sys.stderr)
            has_key_newlines = '\n' in SF_PRIVATE_KEY
            print(f"[SF] Private key has newlines: {'Yes' if has_key_newlines else 'No'}", file=sys.stderr)
            # Show first few lines for debugging
            if has_key_newlines:
                key_lines_debug = SF_PRIVATE_KEY.split('\n')[:3]
                print(f"[SF] First 3 lines: {key_lines_debug}", file=sys.stderr)
            
            assertion = jwt.encode(payload, SF_PRIVATE_KEY, algorithm="RS256")
            
            resp = requests.post(
                f"{SF_LOGIN_URL}/services/oauth2/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                timeout=15,
            )
            
            if resp.status_code != 200:
                raise RuntimeError(f"Auth failed: {resp.status_code} - {resp.text}")
            
            data = resp.json()
            _sf_client = Salesforce(
                instance_url=data["instance_url"],
                session_id=data["access_token"],
            )
            _auth_time = time.time()
            print(f"[SF] Authenticated in {time.time()-t:.1f}s", file=sys.stderr)
        except Exception as e:
            print(f"[SF ERROR] Authentication failed: {e}", file=sys.stderr)
            raise
    
    return _sf_client

