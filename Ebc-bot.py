import os
import asyncio
from deriv_api import DerivAPI

TOKEN = os.getenv('DERIV_API_TOKEN')
APP_ID = "1089"

async def main():
    print(f"TOKEN exists: {bool(TOKEN)}")
    if not TOKEN:
        print("❌ ERROR: DERIV_API_TOKEN environment variable is not set.")
        return

    print(f"🚀 Connecting to Deriv (demo mode)...")
    api = DerivAPI(app_id=APP_ID)

    try:
        resp = await api.authorize(TOKEN)
        print(f"✅ Authorized: {resp.get('authorize', {}).get('email')}")
        balance = await api.balance()
        print(f"💰 Balance: ${balance['balance']['balance']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await api.clear()

if __name__ == "__main__":
    asyncio.run(main())
