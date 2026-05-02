import os
import requests
import time
import json

TOKEN = os.getenv('DERIV_API_TOKEN')
APP_ID = "1089"

def deriv_request(payload):
    url = f"https://api.deriv.com/websockets/v3?app_id={APP_ID}"
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Request error: {e}")
        return None

def main():
    print("🚀 EBC Bot starting...")
    
    if not TOKEN:
        print("❌ Missing DERIV_API_TOKEN environment variable.")
        return
    
    # Authorize
    print("🔐 Authorizing...")
    result = deriv_request({"authorize": TOKEN})
    
    if not result or 'error' in result:
        error_msg = result.get('error', {}).get('message', 'Unknown error') if result else "No response"
        print(f"❌ Authorization failed: {error_msg}")
        return
    
    print(f"✅ Authorized: {result['authorize']['email']}")
    
    # Get balance
    print("💰 Fetching balance...")
    balance_result = deriv_request({"balance": 1})
    
    if balance_result and 'balance' in balance_result:
        print(f"💰 Balance: ${balance_result['balance']['balance']}")
    else:
        print("⚠️ Could not fetch balance")
    
    print("🎉 Bot is running successfully!")

if __name__ == "__main__":
    main()
