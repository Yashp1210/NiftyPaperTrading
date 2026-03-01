"""
Nifty 50 Paper Trading System - Flask Backend
Automated signal detection + paper trade journal + Telegram alerts
Zerodha OAuth 2.0 Compatible with DEBUG LOGGING
UPDATED STRATEGY: Breakout Confirmation + 20 EMA Filter + Professional Risk Management
Author: Yash Patel | GitHub: Yashp1210
"""

from flask import Flask, request, jsonify, send_from_directory, redirect, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import jwt
import os
from datetime import datetime, timedelta
import json
import requests
import schedule
import threading
from dotenv import load_dotenv
import sqlite3
from kiteconnect import KiteConnect
import logging
from urllib.parse import urlencode
import hashlib
import traceback
import calendar

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///paper_trades.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-prod')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

CORS(app, supports_credentials=True)
db = SQLAlchemy(app)

# Logging setup - VERBOSE DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log startup configuration
logger.info("=" * 100)
logger.info("🚀 NIFTY PAPER TRADING STARTUP - UPDATED STRATEGY")
logger.info("=" * 100)
logger.info(f"KITE_API_KEY configured: {bool(os.getenv('KITE_API_KEY'))}")
logger.info(f"KITE_API_SECRET configured: {bool(os.getenv('KITE_API_SECRET'))}")
logger.info(f"KITE_REDIRECT_URL: {os.getenv('KITE_REDIRECT_URL')}")
logger.info(f"Strategy: Breakout + 20 EMA + Size 70-250 + 1 Trade/Day + Exit 2:45 PM")
logger.info("=" * 100)

# Configuration - Zerodha OAuth
KITE_API_KEY = os.getenv('KITE_API_KEY', '')
KITE_API_SECRET = os.getenv('KITE_API_SECRET', '')
KITE_REDIRECT_URL = os.getenv('KITE_REDIRECT_URL', 'http://localhost:5000/callback')
KITE_LOGIN_URL = 'https://kite.zerodha.com/connect/login'
KITE_TOKEN_URL = 'https://api.kite.trade/session/token'
KITE_API_BASE = 'https://api.kite.trade'

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_USER_ID = os.getenv('TELEGRAM_USER_ID', '')

# Global state
current_signal = None
kite_clients = {}  # Store KiteConnect instances per user

# ==================== DATABASE MODELS ====================

class UserSession(db.Model):
    """Store user sessions and Zerodha credentials"""
    __tablename__ = 'user_sessions'

    user_id = db.Column(db.String(100), primary_key=True)
    kite_access_token = db.Column(db.String(500), nullable=False)
    kite_user_id = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    broker = db.Column(db.String(50), default='zerodha')
    token_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'kite_user_id': self.kite_user_id,
            'user_name': self.user_name,
            'email': self.email,
            'broker': self.broker,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class PaperTrade(db.Model):
    """SQLAlchemy model for paper trades"""
    __tablename__ = 'paper_trades'

    trade_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('user_sessions.user_id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    strike = db.Column(db.Integer, nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # CE or PE
    entry_premium = db.Column(db.Float, nullable=False)
    entry_time = db.Column(db.String(20), nullable=False)
    sl_premium = db.Column(db.Float, nullable=False)
    target_premium = db.Column(db.Float, nullable=False)
    exit_premium = db.Column(db.Float, nullable=True)
    exit_time = db.Column(db.String(20), nullable=True)
    pnl = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='open')  # open, closed, target, sl
    candle_high = db.Column(db.Float, nullable=True)
    candle_low = db.Column(db.Float, nullable=True)
    spot_price = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'trade_id': self.trade_id,
            'user_id': self.user_id,
            'date': self.date,
            'strike': self.strike,
            'direction': self.direction,
            'entry_premium': self.entry_premium,
            'entry_time': self.entry_time,
            'sl_premium': self.sl_premium,
            'target_premium': self.target_premium,
            'exit_premium': self.exit_premium,
            'exit_time': self.exit_time,
            'pnl': self.pnl,
            'status': self.status,
            'candle_high': self.candle_high,
            'candle_low': self.candle_low,
            'spot_price': self.spot_price,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ==================== JWT AUTHENTICATION ====================

def token_required(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token is missing!'}), 401

        try:
            token = token.split(' ')[1] if ' ' in token else token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['user_id']
        except Exception as e:
            logger.error(f"Token error: {e}")
            return jsonify({'error': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated

# ==================== ZERODHA OAUTH FLOWS ====================

@app.route('/login', methods=['GET'])
def login():
    """Initiate Zerodha OAuth login"""
    try:
        logger.info("=" * 100)
        logger.info("🔐 /login ENDPOINT CALLED")
        logger.info("=" * 100)

        if not KITE_API_KEY:
            logger.error("❌ KITE_API_KEY not configured!")
            return "ERROR: KITE_API_KEY not set in environment", 500

        logger.info(f"✅ KITE_API_KEY: {KITE_API_KEY[:10]}...")
        logger.info(f"✅ KITE_REDIRECT_URL: {KITE_REDIRECT_URL}")

        params = {
            'api_key': KITE_API_KEY,
            'v': '3'
        }
        login_url = f"{KITE_LOGIN_URL}?{urlencode(params)}"
        logger.info(f"✅ Redirecting to: {login_url[:80]}...")
        logger.info("=" * 100)

        return redirect(login_url)
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Login failed'}), 400

@app.route('/callback', methods=['GET'])
def oauth_callback():
    """Handle Zerodha OAuth callback"""
    try:
        logger.info("=" * 100)
        logger.info("🔄 /callback ENDPOINT CALLED")
        logger.info("=" * 100)

        logger.info(f"📋 Query Parameters: {dict(request.args)}")
        logger.info(f"📋 Request URL: {request.url}")
        logger.info(f"📋 Request Method: {request.method}")

        request_token = request.args.get('request_token')
        logger.info(f"📌 request_token from URL: {request_token[:30] if request_token else 'MISSING'}...")

        if not request_token:
            logger.error("❌ Missing request_token in callback")
            logger.info("=" * 100)
            return jsonify({'error': 'Missing request token'}), 400

        logger.info(f"✅ request_token received: {request_token[:20]}...")

        logger.info(f"🔐 Checking API credentials...")
        logger.info(f"  KITE_API_KEY is set: {bool(KITE_API_KEY)}")
        logger.info(f"  KITE_API_KEY value: {KITE_API_KEY if KITE_API_KEY else 'EMPTY'}")
        logger.info(f"  KITE_API_SECRET is set: {bool(KITE_API_SECRET)}")
        logger.info(f"  KITE_API_SECRET value: {KITE_API_SECRET[:10] if KITE_API_SECRET else 'EMPTY'}...")

        logger.info(f"🔐 Using KiteConnect to generate session...")
        kite = KiteConnect(api_key=KITE_API_KEY)

        try:
            session_data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
            logger.info(f"✅ Session generated successfully")
        except Exception as e:
            logger.error(f"❌ generate_session failed: {e}")
            logger.info("=" * 100)
            return f'''
            <html><body style="font-family: Arial;">
            <h2>❌ OAuth Error: Token Exchange Failed</h2>
            <p><strong>Message:</strong> {str(e)}</p>
            <p><strong>Tip:</strong> Make sure your KITE_API_KEY and KITE_API_SECRET are correct in your .env,
            and the Redirect URL in your Kite app settings at kite.trade/apps exactly matches your server URL.</p>
            <a href="/">← Back to Login</a>
            </body></html>
            ''', 400

        access_token = session_data.get('access_token')
        user_id = session_data.get('user_id')
        user_name = session_data.get('user_name', '')
        email = session_data.get('email', '')

        logger.info(f"✅ Extracted access_token: {access_token[:20] if access_token else 'MISSING'}...")
        logger.info(f"✅ Extracted user_id: {user_id}")
        logger.info(f"✅ Extracted user_name: {user_name}")
        logger.info(f"✅ Extracted email: {email}")

        if not access_token or not user_id:
            logger.error(f"❌ Missing critical data - token: {bool(access_token)}, user_id: {bool(user_id)}")
            logger.info("=" * 100)
            return jsonify({'error': 'Missing access_token or user_id'}), 400

        logger.info(f"✅ Token exchange successful!")

        logger.info(f"💾 Saving to database...")
        user_session = UserSession.query.filter_by(user_id=user_id).first()

        if user_session:
            logger.info(f"✅ Updating existing session for user: {user_id}")
            user_session.kite_access_token = access_token
            user_session.last_login = datetime.utcnow()
        else:
            logger.info(f"✅ Creating new session for user: {user_id}")
            user_session = UserSession(
                user_id=user_id,
                kite_user_id=user_id,
                kite_access_token=access_token,
                user_name=user_name,
                email=email,
                token_expires_at=datetime.utcnow() + timedelta(hours=24)
            )

        db.session.add(user_session)
        db.session.commit()
        logger.info(f"✅ User session saved to database")

        logger.info(f"🔑 Generating JWT token...")
        jwt_token = jwt.encode({
            'user_id': user_id,
            'user_name': user_name,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        logger.info(f"✅ JWT token generated")

        frontend_url = os.getenv('FRONTEND_URL', 'https://niftypapertrading.onrender.com')
        redirect_url = f"{frontend_url}?token={jwt_token}&user_id={user_id}&user_name={user_name}"

        logger.info(f"✅ Redirecting to: {frontend_url}")
        logger.info("=" * 100)

        return redirect(redirect_url)

    except Exception as e:
        logger.error(f"❌ OAuth callback error: {str(e)}")
        logger.error(traceback.format_exc())
        logger.info("=" * 100)
        return jsonify({'error': f'Callback processing failed: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Logout endpoint - invalidate user session"""
    try:
        user_session = UserSession.query.filter_by(user_id=current_user).first()
        if user_session:
            db.session.delete(user_session)
            db.session.commit()

        return jsonify({'status': 'logged out'}), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== KITE API FUNCTIONS ====================

def get_kite_client(user_id):
    """Get or create KiteConnect client for user"""
    global kite_clients

    if user_id in kite_clients:
        return kite_clients[user_id]

    try:
        user_session = UserSession.query.filter_by(user_id=user_id).first()
        if not user_session:
            return None

        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(user_session.kite_access_token)

        kite_clients[user_id] = kite
        logger.info(f"Kite client initialized for user: {user_id}")
        return kite
    except Exception as e:
        logger.error(f"Failed to initialize Kite for {user_id}: {e}")
        return None

def get_nifty_spot(user_id):
    """Fetch current Nifty 50 spot price"""
    try:
        kite = get_kite_client(user_id)
        if not kite:
            return None

        quote = kite.quote(instrument_tokens=['256265'])  # NIFTY 50 token
        if '256265' in quote:
            return quote['256265']['last_price']
        return None
    except Exception as e:
        logger.error(f"Error fetching Nifty spot: {e}")
        return None

def get_first_15min_candle(user_id, date_str):
    """Fetch 9:15-9:30 AM candle data"""
    try:
        kite = get_kite_client(user_id)
        if not kite:
            return None

        candles = kite.historical_data(
            instrument_token=256265,  # NIFTY 50
            from_date=date_str,
            to_date=date_str,
            interval="15minute"
        )

        if candles:
            first_candle = candles[0]
            return {
                'high': first_candle['high'],
                'low': first_candle['low'],
                'open': first_candle['open'],
                'close': first_candle['close']
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching candle: {e}")
        return None

def get_all_15min_candles(user_id, date_str):
    """Fetch all 15-minute candles for the day (for 20 EMA calculation)"""
    try:
        kite = get_kite_client(user_id)
        if not kite:
            return None

        candles = kite.historical_data(
            instrument_token=256265,
            from_date=date_str,
            to_date=date_str,
            interval="15minute"
        )
        return candles if candles else None
    except Exception as e:
        logger.error(f"Error fetching all candles: {e}")
        return None

def calculate_20_ema(candles):
    """Calculate 20 EMA from candles and return current and previous value"""
    if not candles or len(candles) < 20:
        return None, None

    closes = [c['close'] for c in candles]

    # Simple moving average for first 20
    sma = sum(closes[:20]) / 20
    ema_prev = sma

    # EMA calculation
    multiplier = 2 / (20 + 1)

    for close in closes[20:]:
        ema = close * multiplier + ema_prev * (1 - multiplier)
        ema_prev = ema

    ema_current = ema_prev

    # Get the EMA value before the last one for slope comparison
    if len(closes) >= 21:
        ema_prev2 = sma
        for close in closes[20:-1]:
            ema_prev2 = close * multiplier + ema_prev2 * (1 - multiplier)
    else:
        ema_prev2 = ema_current

    return round(ema_current, 2), round(ema_prev2, 2)

def is_ema_bullish(ema_current, ema_previous):
    """Check if EMA trend is bullish (rising)"""
    if ema_current is None or ema_previous is None:
        return False
    return ema_current > ema_previous

def check_breakout(all_candles, first_candle_high, first_candle_low, direction):
    """Check if price breaks out after 9:30 AM (first candle closes)"""
    if not all_candles or len(all_candles) < 2:
        return False

    # Skip first candle (9:15-9:30), check rest of day
    for candle in all_candles[1:]:
        if direction == "CE":
            # For bullish, check if price goes above 9:30 candle high
            if candle['high'] >= first_candle_high:
                return True
        else:  # PE
            # For bearish, check if price goes below 9:30 candle low
            if candle['low'] <= first_candle_low:
                return True

    return False

def get_atm_strike(spot):
    """Calculate ATM strike"""
    return round(spot / 50) * 50

def detect_signal(candle_high, candle_low, spot_price):
    """Detect signal - now candle size check is 70-250"""
    candle_size = candle_high - candle_low

    if candle_size > 250 or candle_size < 70:
        logger.info(f"Candle skipped - size: {candle_size} (must be 70-250)")
        return None

    return None

def send_telegram_alert(user_id, message):
    """Send alert to user's Telegram"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token not configured")
            return False

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_USER_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=5)

        if response.status_code == 200:
            logger.info(f"Telegram alert sent")
            return True
        else:
            logger.error(f"Telegram error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

# ==================== BACKTESTING ENGINE ====================

# NSE Holidays
NSE_HOLIDAYS = {
    "2024-01-22", "2024-01-26", "2024-03-25", "2024-04-09", "2024-04-11",
    "2024-04-14", "2024-04-17", "2024-04-21", "2024-05-01", "2024-05-23",
    "2024-06-17", "2024-07-17", "2024-08-15", "2024-10-02", "2024-10-13",
    "2024-11-01", "2024-11-15", "2024-11-20", "2024-12-25",
    "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10",
    "2025-04-14", "2025-04-18", "2025-05-01", "2025-08-15", "2025-08-27",
    "2025-10-02", "2025-10-20", "2025-10-21", "2025-11-05", "2025-12-25",
}

def get_trading_days(year, month=None, day=None):
    """Returns list of trading day strings"""
    days = []

    if day and month:
        d = f"{year:04d}-{month:02d}-{day:02d}"
        dt = datetime.strptime(d, "%Y-%m-%d")
        if dt.weekday() < 5 and d not in NSE_HOLIDAYS:
            days = [d]

    elif month:
        _, last_day = calendar.monthrange(year, month)
        for d in range(1, last_day + 1):
            date_str = f"{year:04d}-{month:02d}-{d:02d}"
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dt.weekday() < 5 and date_str not in NSE_HOLIDAYS:
                days.append(date_str)

    else:
        for m in range(1, 13):
            _, last_day = calendar.monthrange(year, m)
            for d in range(1, last_day + 1):
                date_str = f"{year:04d}-{m:02d}-{d:02d}"
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.weekday() < 5 and date_str not in NSE_HOLIDAYS:
                    if dt <= datetime.now():
                        days.append(date_str)

    return days

def get_option_historical_data(kite, strike, direction, date_str):
    """Fetch 15-min candle data for a Nifty option"""
    try:
        instruments = kite.instruments("NFO")
        token = None
        trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        for inst in instruments:
            sym = inst['tradingsymbol']
            if (sym.startswith('NIFTY') and
                str(strike) in sym and
                sym.endswith(direction) and
                inst['expiry'] >= trade_date):
                token = inst['instrument_token']
                logger.info(f"Found instrument: {sym} token={token}")
                break

        if not token:
            logger.warning(f"No instrument token for {strike}{direction} on {date_str}")
            return None

        candles = kite.historical_data(
            instrument_token=token,
            from_date=f"{date_str} 09:15:00",
            to_date=f"{date_str} 15:30:00",
            interval="15minute"
        )
        return candles
    except Exception as e:
        logger.error(f"Error fetching option data {strike}{direction}: {e}")
        return None

def simulate_trade_outcome(option_candles, entry_premium, sl_premium, target_premium):
    """Simulate trade candle by candle. Exit at 2:45 PM (14:45)"""
    if not option_candles:
        return entry_premium, "15:30", "closed"

    for candle in option_candles[1:]:
        high = candle['high']
        low = candle['low']
        t = candle['date']
        candle_time = t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[11:16]

        # Check SL first
        if low <= sl_premium:
            return sl_premium, candle_time, "sl"

        # Check target
        if high >= target_premium:
            return target_premium, candle_time, "target"

        # Check 2:45 PM (14:45) forced exit
        if candle_time >= "14:45":
            return round(candle['close'], 1), candle_time, "closed"

    # If nothing hit by EOD
    last = option_candles[-1]
    return round(last['close'], 1), "15:30", "closed"

def run_backtest(user_id, kite, trading_days, period_label):
    """
    Core backtest engine with NEW STRATEGY:
    1. Breakout confirmation
    2. 20 EMA filter
    3. Candle size 70-250
    4. One trade per day
    5. Exit at 2:45 PM
    """
    results = []
    total_pnl = 0
    winners = 0
    losers = 0
    skipped = 0

    logger.info(f"🔁 BACKTEST STARTED: {period_label} | {len(trading_days)} days")

    send_telegram_alert(user_id, f"""📊 <b>BACKTEST STARTED</b>
📅 Period: <b>{period_label}</b>
📆 Trading Days: {len(trading_days)}
Strategy: Breakout + 20 EMA | Size 70-250 | 1 Trade/Day | Exit 2:45 PM""")

    for date_str in trading_days:
        try:
            logger.info(f"\n📅 {date_str}...")

            # STEP 1: Get first candle and check size
            candle = get_first_15min_candle(user_id, date_str)
            if not candle:
                skipped += 1
                logger.warning(f"  No candle data, skipping")
                continue

            candle_high = candle['high']
            candle_low = candle['low']
            candle_open = candle.get('open', candle['close'])
            spot_price = candle['close']
            candle_size = candle_high - candle_low

            # Size filter: 70-250 only
            if candle_size > 250 or candle_size < 70:
                skipped += 1
                send_telegram_alert(user_id,
                    f"⏭ <b>{date_str}</b> — Skipped\nCandle size {candle_size:.0f} pts (needs 70–250)")
                results.append({'date': date_str, 'status': 'skipped', 'reason': f'size {candle_size:.0f}'})
                continue

            # STEP 2: Get all candles and calculate 20 EMA
            all_candles = get_all_15min_candles(user_id, date_str)
            if not all_candles:
                skipped += 1
                send_telegram_alert(user_id, f"⏭ <b>{date_str}</b> — No candle data")
                results.append({'date': date_str, 'status': 'skipped', 'reason': 'no data'})
                continue

            ema_current, ema_previous = calculate_20_ema(all_candles)

            if ema_current is None:
                skipped += 1
                send_telegram_alert(user_id, f"⏭ <b>{date_str}</b> — Not enough data for EMA")
                results.append({'date': date_str, 'status': 'skipped', 'reason': 'insufficient data'})
                continue

            # STEP 3: Determine direction and check EMA match
            candle_is_green = spot_price >= candle_open
            direction = "CE" if candle_is_green else "PE"

            ema_is_bullish = is_ema_bullish(ema_current, ema_previous)

            # Filter: CE only if EMA bullish, PE only if EMA bearish
            if direction == "CE" and not ema_is_bullish:
                skipped += 1
                send_telegram_alert(user_id,
                    f"⏭ <b>{date_str}</b> — Skipped\nCE signal but EMA is bearish (↓)")
                results.append({'date': date_str, 'status': 'skipped', 'reason': 'EMA mismatch'})
                continue

            if direction == "PE" and ema_is_bullish:
                skipped += 1
                send_telegram_alert(user_id,
                    f"⏭ <b>{date_str}</b> — Skipped\nPE signal but EMA is bullish (↑)")
                results.append({'date': date_str, 'status': 'skipped', 'reason': 'EMA mismatch'})
                continue

            # STEP 4: Check breakout confirmation
            has_breakout = check_breakout(all_candles, candle_high, candle_low, direction)

            if not has_breakout:
                skipped += 1
                send_telegram_alert(user_id,
                    f"⏭ <b>{date_str}</b> — Skipped\nNo breakout after 9:30 AM")
                results.append({'date': date_str, 'status': 'skipped', 'reason': 'no breakout'})
                continue

            # STEP 5: Calculate strike and entry
            strike = get_atm_strike(spot_price)

            option_candles = get_option_historical_data(kite, strike, direction, date_str)
            if option_candles and len(option_candles) > 0:
                entry_premium = round(option_candles[0]['close'], 1)
            else:
                entry_premium = round(spot_price * 0.015, 1)

            # NEW: Fixed SL and Target
            sl_premium = round(max(entry_premium - 100, 10), 1)
            target_premium = round(entry_premium + 150, 1)

            # STEP 6: Send ENTRY alert (simplified)
            send_telegram_alert(user_id, f"""
🚨 <b>TRADE SIGNAL — {date_str}</b>

📌 {"🟢 BUY CE" if direction == "CE" else "🔴 SELL PE"} | <b>NIFTY {strike} {direction}</b>

💰 <b>BUY:</b> ₹{entry_premium}
🛑 <b>SL:</b> ₹{sl_premium}
🎯 <b>TARGET:</b> ₹{target_premium}

📊 EMA: {"↑ Bullish" if ema_is_bullish else "↓ Bearish"} | Candle: {candle_size:.0f} pts""")

            # STEP 7: Simulate outcome
            exit_premium, exit_time, trade_status = simulate_trade_outcome(
                option_candles, entry_premium, sl_premium, target_premium)

            pnl = round((exit_premium - entry_premium) * 50, 2)
            total_pnl += pnl
            if pnl > 0: winners += 1
            else: losers += 1

            # STEP 8: Send EXIT alert
            if trade_status == "target":
                exit_emoji, exit_label = "🎯", "TARGET HIT ✅"
            elif trade_status == "sl":
                exit_emoji, exit_label = "🛑", "STOP LOSS ❌"
            else:
                exit_emoji, exit_label = "🕐", "CLOSED AT 2:45 PM"

            send_telegram_alert(user_id, f"""
{exit_emoji} <b>{exit_label} — {date_str}</b>

NIFTY {strike} {direction}
₹{entry_premium} → ₹{exit_premium}
⏰ {exit_time}

{"📈" if pnl >= 0 else "📉"} <b>P&L: ₹{pnl:+,.0f}</b>""")

            # Save to DB
            trade_id = f"BT_{date_str}_{direction}"
            if not PaperTrade.query.filter_by(trade_id=trade_id).first():
                db.session.add(PaperTrade(
                    trade_id=trade_id, user_id=user_id, date=date_str,
                    strike=strike, direction=direction,
                    entry_premium=entry_premium, entry_time="09:30:00",
                    sl_premium=sl_premium, target_premium=target_premium,
                    exit_premium=exit_premium, exit_time=exit_time,
                    pnl=pnl, status=trade_status,
                    candle_high=candle_high, candle_low=candle_low, spot_price=spot_price
                ))
                db.session.commit()

            results.append({
                'date': date_str, 'direction': direction, 'strike': strike,
                'entry': entry_premium, 'sl': sl_premium, 'target': target_premium,
                'exit': exit_premium, 'exit_time': exit_time,
                'status': trade_status, 'pnl': pnl
            })

            logger.info(f"  {trade_status.upper()} | P&L: ₹{pnl:+.0f} | Total: ₹{total_pnl:+.0f}")

        except Exception as e:
            logger.error(f"Error on {date_str}: {e}")
            results.append({'date': date_str, 'status': 'error', 'reason': str(e)})

    # Final summary
    total_trades = winners + losers
    win_rate = round(winners / total_trades * 100, 1) if total_trades else 0

    send_telegram_alert(user_id, f"""
📊 <b>BACKTEST COMPLETE — {period_label}</b>

━━━━━━━━━━━━━━━━━━━━
✅ Trades: {total_trades}
🏆 Wins: {winners}
❌ Losses: {losers}
⏭ Skipped: {skipped}

📊 Win Rate: <b>{win_rate}%</b>

💰 <b>TOTAL P&L (1 Lot): ₹{total_pnl:+,.0f}</b>
━━━━━━━━━━━━━━━━━━━━""")

    return {
        'period': period_label, 'total_trades': total_trades,
        'winners': winners, 'losers': losers, 'skipped': skipped,
        'win_rate': win_rate, 'total_pnl': round(total_pnl, 2),
        'results': results
    }

# ==================== API ROUTES ====================

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile(current_user):
    """Get current user profile"""
    try:
        user = UserSession.query.filter_by(user_id=current_user).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify(user.to_dict()), 200
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trade', methods=['POST'])
@token_required
def create_trade(current_user):
    """Create a new paper trade"""
    try:
        data = request.json
        trade_id = f"{current_user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        new_trade = PaperTrade(
            trade_id=trade_id,
            user_id=current_user,
            date=data['date'],
            strike=data['strike'],
            direction=data['direction'],
            entry_premium=data['entry_premium'],
            entry_time=datetime.now().strftime('%H:%M:%S'),
            sl_premium=data['sl_premium'],
            target_premium=data['target_premium'],
            candle_high=data.get('candle_high', 0),
            candle_low=data.get('candle_low', 0),
            spot_price=data.get('spot_price', 0)
        )

        db.session.add(new_trade)
        db.session.commit()

        # Send Telegram alert
        msg = f"""
✅ <b>TRADE ENTERED</b>
Strike: {data['strike']} {data['direction']}
Entry: ₹{data['entry_premium']}
SL: ₹{data['sl_premium']}
Target: ₹{data['target_premium']}
Time: {new_trade.entry_time}
        """
        send_telegram_alert(current_user, msg)

        return jsonify({
            'trade_id': trade_id,
            'status': 'created',
            'trade': new_trade.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Trade creation error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/trade/<trade_id>/close', methods=['PUT'])
@token_required
def close_trade(current_user, trade_id):
    """Close a trade with exit premium"""
    try:
        trade = PaperTrade.query.filter_by(trade_id=trade_id, user_id=current_user).first()

        if not trade:
            return jsonify({'error': 'Trade not found'}), 404

        data = request.json
        exit_premium = data['exit_premium']

        # Calculate P&L
        pnl = (exit_premium - trade.entry_premium) * 50  # 1 lot = 50 qty

        # Determine status
        if exit_premium >= trade.target_premium:
            status = 'target'
        elif exit_premium <= trade.sl_premium:
            status = 'sl'
        else:
            status = 'closed'

        # Update trade
        trade.exit_premium = exit_premium
        trade.exit_time = datetime.now().strftime('%H:%M:%S')
        trade.pnl = pnl
        trade.status = status

        db.session.commit()

        # Send Telegram alert
        emoji = '✅' if pnl >= 0 else '❌'
        msg = f"""
{emoji} <b>TRADE {status.upper()}</b>
Strike: {trade.strike} {trade.direction}
Entry: ₹{trade.entry_premium} → Exit: ₹{exit_premium}
P&L: ₹{pnl}
Time: {trade.exit_time}
        """
        send_telegram_alert(current_user, msg)

        return jsonify({
            'trade_id': trade_id,
            'status': 'closed',
            'pnl': pnl,
            'trade': trade.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Trade close error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades', methods=['GET'])
@token_required
def get_trades(current_user):
    """Get all trades for current user"""
    try:
        date_filter = request.args.get('date')
        status_filter = request.args.get('status')

        query = PaperTrade.query.filter_by(user_id=current_user)

        if date_filter:
            query = query.filter_by(date=date_filter)

        if status_filter:
            query = query.filter_by(status=status_filter)

        trades = query.order_by(PaperTrade.date.desc()).all()

        return jsonify({
            'total': len(trades),
            'trades': [trade.to_dict() for trade in trades]
        }), 200

    except Exception as e:
        logger.error(f"Get trades error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/journal', methods=['GET'])
@token_required
def get_journal(current_user):
    """Get journal grouped by day/month/year"""
    try:
        view = request.args.get('view', 'day')  # day, month, year
        trades = PaperTrade.query.filter_by(user_id=current_user).order_by(PaperTrade.date.desc()).all()

        grouped = {}

        for trade in trades:
            if view == 'day':
                key = trade.date
            elif view == 'month':
                key = trade.date[:7]
            else:
                key = trade.date[:4]

            if key not in grouped:
                grouped[key] = {
                    'period': key,
                    'trades': [],
                    'total_trades': 0,
                    'total_pnl': 0,
                    'winners': 0,
                    'losers': 0
                }

            grouped[key]['trades'].append(trade.to_dict())
            grouped[key]['total_trades'] += 1
            if trade.pnl:
                grouped[key]['total_pnl'] += trade.pnl
                if trade.pnl > 0:
                    grouped[key]['winners'] += 1
                else:
                    grouped[key]['losers'] += 1

        return jsonify({
            'view': view,
            'data': list(grouped.values())
        }), 200

    except Exception as e:
        logger.error(f"Journal error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    """Get trading statistics"""
    try:
        trades = PaperTrade.query.filter_by(user_id=current_user).all()

        total_trades = len(trades)
        closed_trades = [t for t in trades if t.status in ['closed', 'target', 'sl']]
        winners = [t for t in closed_trades if t.pnl and t.pnl > 0]
        losers = [t for t in closed_trades if t.pnl and t.pnl < 0]

        total_pnl = sum([t.pnl for t in closed_trades if t.pnl])
        win_rate = (len(winners) / len(closed_trades) * 100) if closed_trades else 0

        # Equity curve data
        equity = 0
        equity_curve = []

        for trade in sorted(trades, key=lambda x: x.created_at):
            if trade.pnl:
                equity += trade.pnl
            equity_curve.append({
                'date': trade.date,
                'equity': equity,
                'pnl': trade.pnl if trade.pnl else 0
            })

        return jsonify({
            'total_trades': total_trades,
            'closed_trades': len(closed_trades),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_win': round(sum([t.pnl for t in winners]) / len(winners), 2) if winners else 0,
            'avg_loss': round(sum([t.pnl for t in losers]) / len(losers), 2) if losers else 0,
            'equity_curve': equity_curve
        }), 200

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backtest', methods=['POST'])
@token_required
def run_backtest_api(current_user):
    """Dynamic backtest endpoint"""
    try:
        kite = get_kite_client(current_user)
        if not kite:
            return jsonify({'error': 'Zerodha not connected. Please login first.'}), 401

        data = request.json or {}
        year  = int(data.get('year',  datetime.now().year))
        month = data.get('month')
        day   = data.get('day')

        # Build label and trading days list
        if day and month:
            month = int(month); day = int(day)
            period_label = f"{day:02d} {calendar.month_name[month]} {year}"
        elif month:
            month = int(month)
            period_label = f"{calendar.month_name[month]} {year}"
            day = None
        else:
            period_label = f"Full Year {year}"
            month = None; day = None

        trading_days = get_trading_days(year, month, day)

        if not trading_days:
            return jsonify({'error': 'No trading days found for the given period'}), 400

        # Run in background thread
        def backtest_thread():
            with app.app_context():
                run_backtest(current_user, kite, trading_days, period_label)

        thread = threading.Thread(target=backtest_thread)
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'started',
            'period': period_label,
            'trading_days': len(trading_days),
            'message': f'Backtest started for {period_label}! Watch Telegram for alerts.'
        }), 200

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backtest/results', methods=['GET'])
@token_required
def get_backtest_results(current_user):
    """Get backtest results"""
    try:
        year  = request.args.get('year')
        month = request.args.get('month')
        day   = request.args.get('day')

        query = PaperTrade.query.filter(
            PaperTrade.user_id == current_user,
            PaperTrade.trade_id.like('BT_%')
        )

        if year and month and day:
            prefix = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            query = query.filter(PaperTrade.date == prefix)
        elif year and month:
            prefix = f"{int(year):04d}-{int(month):02d}"
            query = query.filter(PaperTrade.date.like(f"{prefix}%"))
        elif year:
            prefix = f"{int(year):04d}"
            query = query.filter(PaperTrade.date.like(f"{prefix}%"))

        trades = query.order_by(PaperTrade.date.asc()).all()

        closed  = [t for t in trades if t.status in ['target', 'sl', 'closed']]
        winners = [t for t in closed if t.pnl and t.pnl > 0]
        losers  = [t for t in closed if t.pnl and t.pnl <= 0]
        total_pnl = sum(t.pnl for t in closed if t.pnl)
        win_rate  = round(len(winners) / len(closed) * 100, 1) if closed else 0

        return jsonify({
            'total_trades': len(closed),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': win_rate,
            'total_pnl': round(total_pnl, 2),
            'trades': [t.to_dict() for t in trades]
        }), 200

    except Exception as e:
        logger.error(f"Get backtest results error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '3.0',
        'strategy': 'Breakout + 20 EMA + Professional Risk',
        'oauth': 'zerodha'
    }), 200

@app.route('/', methods=['GET'])
def serve_frontend():
    """Serve HTML dashboard"""
    try:
        with open('dashboard.html', 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'text/html'}
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        return jsonify({'message': 'API available'}), 200

# ==================== INITIALIZATION ====================

# Create tables on startup
with app.app_context():
    db.create_all()
    logger.info("✅ Database tables created/verified")

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_ENV', 'production') == 'development'
    )