import os
import json
import websocket

TOKEN = os.getenv('DERIV_API_TOKEN')
APP_ID = "1089"

def on_message(ws, message):
    data = json.loads(message)
    if 'authorize' in data:
        print(f"✅ Authorized: {data['authorize']['email']}")
        ws.send(json.dumps({"balance": 1}))
    elif 'balance' in data:
        print(f"💰 Balance: ${data['balance']['balance']}")
        ws.close()
    elif 'error' in data:
        print(f"❌ Error: {data['error']['message']}")
        ws.close()

def on_error(ws, error):
    print(f"⚠️ WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed")

def on_open(ws):
    print("🔐 Authorizing...")
    ws.send(json.dumps({"authorize": TOKEN}))

def main():
    print("🚀 EBC Bot starting...")
    if not TOKEN:
        print("❌ Missing DERIV_API_TOKEN environment variable.")
        return

    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()

if __name__ == "__main__":
    main()
