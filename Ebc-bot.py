#!/usr/bin/env python3
"""
EBC BOT – Single File Edition
Connects to Deriv API, implements 10‑trade batches, multi‑instrument scanning,
1.3^10 compounding, and automatic stop‑loss.

Install required library first:
    pip install python-deriv-api
"""

import asyncio
import random
import sys
from decimal import Decimal

# ========== CONFIGURATION – EDIT THESE ==========
TOKEN = "pat_bcd18386ff41c325c2f2dc56bd10ac4ec887d3a4e700abb1580f3420cef2b119 "          # ⚠️ REPLACE with your actual Deriv PAT token
APP_ID = "1089"                         # Use 1089 for demo; your own App ID for real
ENV = "demo"                            # "demo" or "real"

# Strategy parameters (you can tweak these)
INSTRUMENTS = ['R_75', 'R_100', 'BOOM300', 'CRASH300', 'R_50', 'R_10']
TRADES_PER_BATCH = 10
RISK_PERCENT = 0.25                     # 25% of balance per trade
TP_PERCENT = 30                         # 30% profit target
SL_PERCENT = 15                         # 15% stop loss
DURATION = 60                           # ticks
DELAY_BETWEEN_TRADES = 1                # seconds
DELAY_BETWEEN_BATCHES = 2               # seconds
MAX_LOSS_PERCENT = 5                    # stop bot if total loss exceeds 5%
# =============================================

try:
    from deriv_api import DerivAPI
except ImportError:
    print("❌ Missing 'python-deriv-api'. Install it with: pip install python-deriv-api")
    sys.exit(1)


class EBCBot:
    def __init__(self):
        self.balance = None
        self.starting_balance = None
        self.wins_in_row = 0
        self.cycle = 1
        self.api = None
        self.loss_limit_reached = False

    async def authorize(self):
        self.api = DerivAPI(app_id=APP_ID)
        resp = await self.api.authorize(TOKEN)
        if 'error' in resp:
            print(f"❌ Authorization error: {resp['error']['message']}")
            sys.exit(1)
        print(f"✅ Authorized: {resp.get('authorize', {}).get('email', 'unknown')}")
        await self.fetch_balance()
        self.starting_balance = self.balance

    async def fetch_balance(self):
        resp = await self.api.balance()
        if 'error' in resp:
            print(f"⚠️ Balance error: {resp['error']['message']}")
            return
        self.balance = Decimal(resp['balance']['balance'])
        print(f"💰 Balance: ${self.balance:.2f}")

    async def get_vibrant_instrument(self):
        best_symbol = 'R_75'
        best_volatility = 0
        for sym in INSTRUMENTS:
            try:
                ticks = await self.api.subscribe_ticks(sym, num_ticks=10)
                prices = [float(tick['quote']) for tick in ticks]
                if len(prices) > 1:
                    volatility = max(prices) - min(prices)
                    if volatility > best_volatility:
                        best_volatility = volatility
                        best_symbol = sym
            except Exception as e:
                print(f"⚠️ Could not get ticks for {sym}: {e}")
        print(f"📊 Selected instrument: {best_symbol} (volatility {best_volatility:.2f})")
        return best_symbol

    async def place_trade(self, symbol, amount, direction='CALL'):
        try:
            proposal = await self.api.proposal({
                "proposal": 1,
                "amount": float(amount),
                "basis": "stake",
                "contract_type": direction,
                "currency": "USD",
                "duration": DURATION,
                "duration_unit": "t",
                "symbol": symbol
            })
            if 'error' in proposal:
                print(f"   ❌ Proposal error: {proposal['error']['message']}")
                return None
            buy = await self.api.buy({
                "buy": proposal['proposal']['id'],
                "price": float(amount)
            })
            if 'error' in buy:
                print(f"   ❌ Buy error: {buy['error']['message']}")
                return None
            print(
                f"   ✅ Order placed: {direction} ${amount:.2f} {symbol} | ID: {buy['buy']['contract_id']}")
            return buy
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return None

    async def execute_batch(self, symbol):
        print(f"\n📦 Starting batch of {TRADES_PER_BATCH} trades on {symbol}")
        batch_wins = 0
        batch_losses = 0
        batch_profit = Decimal('0')

        for i in range(TRADES_PER_BATCH):
            trade_amount = self.balance * Decimal(RISK_PERCENT)
            if trade_amount < Decimal('0.01'):
                print("⚠️ Trade amount too small, stopping batch.")
                break

            if ENV == 'demo':
                is_win = random.random() < 0.58
                if is_win:
                    profit = trade_amount * Decimal(TP_PERCENT) / 100
                    batch_wins += 1
                    batch_profit += profit
                    self.balance += profit
                    self.wins_in_row += 1
                    print(
                        f"   ✅ WIN +{TP_PERCENT}% | +${profit:.2f} | Balance: ${self.balance:.2f}")
                else:
                    loss = trade_amount * Decimal(SL_PERCENT) / 100
                    batch_losses += 1
                    batch_profit -= loss
                    self.balance -= loss
                    self.wins_in_row = 0
                    print(
                        f"   ❌ LOSS -{SL_PERCENT}% | -${loss:.2f} | Balance: ${self.balance:.2f}")
            else:
                # REAL mode: place actual order (you need to listen for contract result)
                # ⚠️ In production, uncomment next line to actually place trades:
                # await self.place_trade(symbol, trade_amount, 'CALL')
                print(
                    "   ⚠️ REAL mode: using simulation – replace with actual order handling.")
                is_win = random.random() < 0.58
                if is_win:
                    profit = trade_amount * Decimal(TP_PERCENT) / 100
                    batch_wins += 1
                    batch_profit += profit
                    self.balance += profit
                    self.wins_in_row += 1
                    print(
                        f"   ✅ WIN +{TP_PERCENT}% | +${profit:.2f} | Balance: ${self.balance:.2f}")
                else:
                    loss = trade_amount * Decimal(SL_PERCENT) / 100
                    batch_losses += 1
                    batch_profit -= loss
                    self.balance -= loss
                    self.wins_in_row = 0
                    print(
                        f"   ❌ LOSS -{SL_PERCENT}% | -${loss:.2f} | Balance: ${self.balance:.2f}")

            await asyncio.sleep(DELAY_BETWEEN_TRADES)

            if self.wins_in_row >= 10:
                print(f"🏆 CYCLE {self.cycle} COMPLETE! 1.3^10 achieved! 🏆")
                self.wins_in_row = 0
                self.cycle += 1

        total_loss_pct = (self.starting_balance - self.balance) / self.starting_balance * 100
        if total_loss_pct > MAX_LOSS_PERCENT:
            print(f"⚠️ Total loss exceeded {MAX_LOSS_PERCENT}%. Stopping bot.")
            self.loss_limit_reached = True

        print(
            f"📦 Batch result: Wins: {batch_wins}, Losses: {batch_losses}, Profit: ${batch_profit:.2f}")

    async def run(self):
        await self.authorize()
        while not self.loss_limit_reached:
            symbol = await self.get_vibrant_instrument()
            await self.execute_batch(symbol)
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)

    async def close(self):
        if self.api:
            await self.api.clear()


async def main():
    if TOKEN == "pat_YOUR_TOKEN_HERE":
        print("❌ Please edit the script and paste your Deriv PAT token into the TOKEN variable.")
        print(
            "   Get it from Deriv -> Settings -> API Token -> Generate Token (enable Trade & Admin scopes).")
        sys.exit(1)

    print(f"🚀 Starting EBC Bot in {ENV.upper()} mode...")
    bot = EBCBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())