import os
import asyncio
from deriv_api import DerivAPI
TOKEN =  )
APP_ID = "1089"
ENV = "demo"   # Change to "real" later

async def main():
    if not TOKEN:
        print("❌ Missing DERIV_API_TOKEN environment variable.")
        return

    print(f"🚀 Starting bot in {ENV.upper()} mode...")
    api = DerivAPI(app_id=APP_ID)

    resp = await api.authorize(TOKEN)
    if 'error' in resp:
        print(f"❌ Authorization failed: {resp['error']['message']}")
        return
    print(f"✅ Authorized: {resp.get('authorize', {}).get('email')}")

    balance = await api.balance()
    print(f"💰 Balance: ${balance['balance']['balance']}")

    await api.clear()

if __name__ == "__main__":
    asyncio.run(main())
