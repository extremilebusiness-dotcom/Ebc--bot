import os
import json
import secrets
import requests
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session, url_for
from flask_session import Session
from websocket import create_connection
import threading
import time

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Deriv OAuth 2.0 Configuration
DERIV_OAUTH = {
    'client_id': os.getenv('DERIV_CLIENT_ID'),
    'client_secret': os.getenv('DERIV_CLIENT_SECRET'),
    'auth_url': 'https://auth.deriv.com/oauth2/auth',
    'token_url': 'https://auth.deriv.com/oauth2/token',
    'redirect_uri': os.getenv('DERIV_REDIRECT_URI'),  # e.g., https://your-app.onrender.com/callback
    'scope': 'read trade account_manage'
}

# Trading constants
INSTRUMENTS = ['R_75', 'R_100', 'BOOM300', 'CRASH300', 'R_50', 'R_10']
TRADES_PER_BATCH = 10
RISK_PERCENT = 0.25    # 25% of balance per trade
TP_PERCENT = 30
SL_PERCENT = 15
DELAY_BETWEEN_TRADES = 1        # seconds
DELAY_BETWEEN_BATCHES = 2
MAX_LOSS_PERCENT = 5

# Store active trading threads (simple in-memory)
active_trades = {}

def deriv_api_request(access_token, payload):
    """Make a Deriv API call using WebSocket (authenticated)"""
    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id=1089"
    ws = create_connection(ws_url)
    try:
        ws.send(json.dumps({"authorize": access_token}))
        auth_resp = json.loads(ws.recv())
        if 'error' in auth_resp:
            raise Exception(f"Auth error: {auth_resp['error']['message']}")
        ws.send(json.dumps(payload))
        resp = json.loads(ws.recv())
        return resp
    finally:
        ws.close()

def get_balance(access_token):
    resp = deriv_api_request(access_token, {"balance": 1})
    if 'balance' in resp:
        return float(resp['balance']['balance'])
    return None

def place_trade(access_token, symbol, amount, direction='CALL'):
    proposal = deriv_api_request(access_token, {
        "proposal": 1,
        "amount": amount,
        "basis": "stake",
        "contract_type": direction,
        "currency": "USD",
        "duration": 60,
        "duration_unit": "t",
        "symbol": symbol
    })
    if 'error' in proposal:
        return None
    buy = deriv_api_request(access_token, {
        "buy": proposal['proposal']['id'],
        "price": amount
    })
    return buy

def trading_loop(user_id, access_token, refresh_token):
    """Continuous trading loop for a user (runs in background thread)"""
    balance = get_balance(access_token)
    if not balance:
        return
    start_balance = balance
    wins_in_row = 0
    cycle = 1
    while True:
        # Refresh token if needed (simple check – token validity ~1 hour)
        # This is a placeholder; implement proper refresh logic
        if datetime.now().timestamp() > session.get('token_expiry', 0):
            new_tokens = refresh_oauth_token(refresh_token)
            if new_tokens:
                access_token = new_tokens['access_token']
                refresh_token = new_tokens['refresh_token']
                # Update session (not used in thread; production would use DB)
            else:
                break

        # Choose most vibrant instrument (simple volatility placeholder)
        symbol = INSTRUMENTS[cycle % len(INSTRUMENTS)]  # rotate for now

        batch_wins = 0
        batch_losses = 0
        batch_profit = 0

        for i in range(TRADES_PER_BATCH):
            trade_amount = balance * RISK_PERCENT
            if trade_amount < 0.01:
                break

            # Place real trade
            order = place_trade(access_token, symbol, trade_amount, 'CALL')
            if order and 'error' not in order:
                # Simulate result for demo; in production you must wait for contract outcome
                # For simplicity, we simulate 58% win rate. Replace with actual contract result.
                is_win = (hash(order['buy']['contract_id']) % 100) < 58
            else:
                is_win = False

            if is_win:
                profit = trade_amount * (TP_PERCENT / 100)
                balance += profit
                batch_wins += 1
                wins_in_row += 1
                print(f"✅ WIN +{TP_PERCENT}% on {symbol} | +${profit:.2f} | Balance: ${balance:.2f}")
            else:
                loss = trade_amount * (SL_PERCENT / 100)
                balance -= loss
                batch_losses += 1
                wins_in_row = 0
                print(f"❌ LOSS -{SL_PERCENT}% on {symbol} | -${loss:.2f} | Balance: ${balance:.2f}")

            batch_profit += (profit if is_win else -loss)
            time.sleep(DELAY_BETWEEN_TRADES)

            if wins_in_row >= 10:
                print(f"🏆 CYCLE {cycle} COMPLETE! 1.3^10 achieved!")
                wins_in_row = 0
                cycle += 1

        print(f"📦 Batch result: Wins {batch_wins}, Losses {batch_losses}, Profit ${batch_profit:.2f}")
        print(f"💰 New balance: ${balance:.2f}")

        # Stop if total loss exceeds MAX_LOSS_PERCENT
        if balance < start_balance * (1 - MAX_LOSS_PERCENT/100):
            print(f"⚠️ Loss limit reached. Stopping bot.")
            break

        time.sleep(DELAY_BETWEEN_BATCHES)

    # Trading loop finished – remove from active dict
    if user_id in active_trades:
        del active_trades[user_id]

def refresh_oauth_token(refresh_token):
    """Exchange refresh token for new access token"""
    data = {
        'client_id': DERIV_OAUTH['client_id'],
        'client_secret': DERIV_OAUTH['client_secret'],
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    resp = requests.post(DERIV_OAUTH['token_url'], data=data)
    if resp.status_code == 200:
        tokens = resp.json()
        return {
            'access_token': tokens['access_token'],
            'refresh_token': tokens.get('refresh_token', refresh_token),
            'expires_in': tokens['expires_in']
        }
    return None

@app.route('/')
def index():
    if not session.get('access_token'):
        return '<a href="/login">Login with Deriv</a> to start trading.'
    return f"""
    <h1>EBC Bot Active</h1>
    <p>User: {session.get('email')}</p>
    <p>Balance: ${session.get('balance', 'loading...')}</p>
    <a href="/start_trading">Start Trading (10‑trade batches)</a><br>
    <a href="/logout">Logout</a><br>
    <a href="/status">Check status</a>
    """

@app.route('/login')
def login():
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    auth_url = (
        f"{DERIV_OAUTH['auth_url']}?"
        f"response_type=code&client_id={DERIV_OAUTH['client_id']}&"
        f"redirect_uri={DERIV_OAUTH['redirect_uri']}&"
        f"scope={DERIV_OAUTH['scope']}&state={state}"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    # Verify state
    if request.args.get('state') != session.get('oauth_state'):
        return "State mismatch. Possible CSRF.", 400
    code = request.args.get('code')
    if not code:
        return "No code provided.", 400

    # Exchange code for tokens
    data = {
        'client_id': DERIV_OAUTH['client_id'],
        'client_secret': DERIV_OAUTH['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DERIV_OAUTH['redirect_uri']
    }
    resp = requests.post(DERIV_OAUTH['token_url'], data=data)
    if resp.status_code != 200:
        return f"Token exchange failed: {resp.text}", 500
    tokens = resp.json()
    session['access_token'] = tokens['access_token']
    session['refresh_token'] = tokens['refresh_token']
    session['token_expiry'] = datetime.now().timestamp() + tokens['expires_in']

    # Get user email via authorized call
    user_info = deriv_api_request(tokens['access_token'], {"authorize": tokens['access_token']})
    if 'error' not in user_info:
        session['email'] = user_info['authorize']['email']

    return redirect(url_for('index'))

@app.route('/start_trading')
def start_trading():
    if not session.get('access_token'):
        return redirect(url_for('index'))
    user_id = session.get('email', 'anonymous')
    if user_id in active_trades:
        return "Trading already active for this user."
    # Start background thread
    thread = threading.Thread(target=trading_loop, args=(user_id, session['access_token'], session['refresh_token']))
    thread.daemon = True
    thread.start()
    active_trades[user_id] = thread
    return "Trading started! Check logs for updates."

@app.route('/status')
def status():
    if not session.get('access_token'):
        return redirect(url_for('index'))
    user_id = session.get('email', 'anonymous')
    if user_id in active_trades:
        return "Trading is active."
    else:
        return "No active trading thread."

@app.route('/logout')
def logout():
    session.clear()
    return "Logged out."

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
