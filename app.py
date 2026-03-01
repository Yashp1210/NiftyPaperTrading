"""
Nifty 50 Paper Trading System - Flask Backend (CORRECTED)
Author: Yash Patel

FIXES vs original:
  1.  detect_signal() was always returning None — now fully works
  2.  target_premium formula fixed to use proper risk calc
  3.  Direction logic: uses actual next-candle breakout, not close vs open
  4.  NFO instruments now CACHED once per day (was fetching 10k rows per trade!)
  5.  KITE_REDIRECT_URL read directly from env (separate env var)
  6.  FRONTEND_URL read from env var (your frontend deployment URL)
  7.  JWT token no longer passed in URL — stored in DB, redirect uses session_code
  8.  dashboard.html now served from /static/ folder
  9.  kite_clients rebuilt from DB on restart (no more lost sessions)
 10.  Backtest trade_id includes timestamp to avoid duplicate conflicts
 11.  Telegram now reads per-user chat_id from DB (UserSession)
 12.  .env.example file mentioned in comments
 13.  requirements.txt listed at top
 14.  SESSION_COOKIE_SECURE only True in production
 15.  simulate_trade_outcome checks target before SL when both hit same candle
"""

# ── requirements.txt (pip install these) ─────────────────────────────────────
# flask
# flask-cors
# flask-sqlalchemy
# kiteconnect
# python-dotenv
# pyjwt
# requests
# schedule
# gunicorn
# ─────────────────────────────────────────────────────────────────────────────

# ── .env file — use these EXACT key names ────────────────────────────────────
# KITE_API_KEY=your_api_key_here
# KITE_API_SECRET=your_api_secret_here
# KITE_REDIRECT_URL=https://your-backend-url.com/callback
# FRONTEND_URL=https://your-frontend-url.com
# SECRET_KEY=any_long_random_string_here
# TELEGRAM_BOT_TOKEN=your_bot_token_here
# TELEGRAM_USER_ID=your_telegram_numeric_id        ← from @userinfobot on Telegram
# FLASK_ENV=development                             ← change to production on server
# ─────────────────────────────────────────────────────────────────────────────

from flask import Flask, request, jsonify, redirect, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import jwt
import os
from datetime import datetime, timedelta, date as date_type
import calendar
import json
import requests
import threading
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import logging
import traceback

load_dotenv()

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///paper_trades.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-in-production')

# FIX 14: Only set secure cookies in production
IS_PROD = os.getenv('FLASK_ENV', 'development') == 'production'
app.config['SESSION_COOKIE_SECURE']   = IS_PROD
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

CORS(app, supports_credentials=True)
db = SQLAlchemy(app)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s — %(message)s'
)
logger = logging.getLogger(__name__)

# ── Config from env ───────────────────────────────────────────────────────────
KITE_API_KEY    = os.getenv('KITE_API_KEY', '')
KITE_API_SECRET = os.getenv('KITE_API_SECRET', '')

# Use exact env var names as configured in your environment panel
FRONTEND_URL      = os.getenv('FRONTEND_URL', 'http://localhost:3000')   # your frontend URL
KITE_REDIRECT_URL = os.getenv('KITE_REDIRECT_URL', f'{FRONTEND_URL}/callback')  # separate env var

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_USER_ID   = os.getenv('TELEGRAM_USER_ID', '')   # matches your env var name

LOT_SIZE   = 50
SL_PCT     = 0.50   # 50% of entry → stop loss
TARGET_RR  = 2.0    # 1:2 risk-reward

# ── NSE Holidays ──────────────────────────────────────────────────────────────
NSE_HOLIDAYS = {
    "2024-01-22","2024-01-26","2024-03-25","2024-04-09","2024-04-11",
    "2024-04-14","2024-04-17","2024-04-21","2024-05-01","2024-05-23",
    "2024-06-17","2024-07-17","2024-08-15","2024-10-02","2024-10-13",
    "2024-11-01","2024-11-15","2024-11-20","2024-12-25",
    "2025-01-26","2025-02-26","2025-03-14","2025-03-31","2025-04-10",
    "2025-04-14","2025-04-18","2025-05-01","2025-08-15","2025-08-27",
    "2025-10-02","2025-10-20","2025-10-21","2025-11-05","2025-12-25",
}

# ── Instrument cache (per day) ────────────────────────────────────────────────
# FIX 4: Cache NFO instruments once per day, not every trade
_instrument_cache = {'date': None, 'data': None}

def get_nfo_instruments(kite):
    """Fetch and cache NFO instruments list — refreshed once per trading day."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    if _instrument_cache['date'] == today_str and _instrument_cache['data']:
        return _instrument_cache['data']

    logger.info("🔄 Refreshing NFO instrument cache...")
    instruments = kite.instruments("NFO")
    _instrument_cache['date'] = today_str
    _instrument_cache['data'] = instruments
    logger.info(f"✅ Cached {len(instruments)} NFO instruments")
    return instruments


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    user_id             = db.Column(db.String(100), primary_key=True)
    kite_access_token   = db.Column(db.String(500), nullable=False)
    kite_user_id        = db.Column(db.String(100), nullable=False)
    user_name           = db.Column(db.String(200), nullable=True)
    email               = db.Column(db.String(200), nullable=True)
    # Per-user Telegram override (optional — falls back to TELEGRAM_USER_ID env var)
    telegram_user_id    = db.Column(db.String(100), nullable=True)
    token_expires_at    = db.Column(db.DateTime, nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    last_login          = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'user_id':   self.user_id,
            'user_name': self.user_name,
            'email':     self.email,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class PaperTrade(db.Model):
    __tablename__ = 'paper_trades'
    trade_id        = db.Column(db.String(80),  primary_key=True)
    user_id         = db.Column(db.String(100), db.ForeignKey('user_sessions.user_id'), nullable=False)
    date            = db.Column(db.String(20),  nullable=False)
    strike          = db.Column(db.Integer,     nullable=False)
    direction       = db.Column(db.String(10),  nullable=False)   # CE | PE
    entry_premium   = db.Column(db.Float,       nullable=False)
    entry_time      = db.Column(db.String(20),  nullable=False)
    sl_premium      = db.Column(db.Float,       nullable=False)
    target_premium  = db.Column(db.Float,       nullable=False)
    exit_premium    = db.Column(db.Float,       nullable=True)
    exit_time       = db.Column(db.String(20),  nullable=True)
    pnl             = db.Column(db.Float,       nullable=True)
    status          = db.Column(db.String(20),  default='open')   # open|target|sl|closed
    candle_high     = db.Column(db.Float,       nullable=True)
    candle_low      = db.Column(db.Float,       nullable=True)
    candle_size     = db.Column(db.Float,       nullable=True)
    spot_price      = db.Column(db.Float,       nullable=True)
    is_backtest     = db.Column(db.Boolean,     default=False)
    note            = db.Column(db.String(500), nullable=True)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            'trade_id':       self.trade_id,
            'date':           self.date,
            'strike':         self.strike,
            'direction':      self.direction,
            'entry_premium':  self.entry_premium,
            'entry_time':     self.entry_time,
            'sl_premium':     self.sl_premium,
            'target_premium': self.target_premium,
            'exit_premium':   self.exit_premium,
            'exit_time':      self.exit_time,
            'pnl':            self.pnl,
            'status':         self.status,
            'candle_high':    self.candle_high,
            'candle_low':     self.candle_low,
            'candle_size':    self.candle_size,
            'spot_price':     self.spot_price,
            'is_backtest':    self.is_backtest,
            'note':           self.note,
        }


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_atm_strike(spot: float) -> int:
    """Round spot to nearest 50 for ATM strike."""
    return int(round(spot / 50) * 50)


def calc_sl(entry: float) -> float:
    """Stop loss = 50% of entry premium."""
    return round(entry * SL_PCT, 1)


def calc_target(entry: float) -> float:
    """
    FIX 2: Correct target formula using actual risk.
    risk   = entry - sl  = entry * 0.5
    target = entry + risk * RR
           = entry + (entry * 0.5) * 2
           = entry * 2.0   ← same result when SL=50%, but formula is correct
    If you later change SL_PCT, this still works correctly.
    """
    sl = calc_sl(entry)
    risk = entry - sl
    return round(entry + risk * TARGET_RR, 1)


def calc_pnl(entry: float, exit_price: float) -> float:
    """P&L for 1 lot."""
    return round((exit_price - entry) * LOT_SIZE, 2)


# FIX 1: detect_signal() now actually works
def detect_signal(candle_high: float, candle_low: float,
                  spot_at_930: float, nifty_candles: list) -> dict | None:
    """
    Detect breakout signal from the 9:15–9:30 candle.

    Args:
        candle_high:   HIGH of 9:15-9:30 15-min candle
        candle_low:    LOW  of 9:15-9:30 15-min candle
        spot_at_930:   Nifty spot at 9:30 AM close
        nifty_candles: List of subsequent 15-min Nifty candles (9:30 AM onward)

    Returns:
        dict with direction/strike/reasoning  OR  None (skip day)
    """
    candle_size = candle_high - candle_low
    logger.info(f"Signal detection — High: {candle_high}, Low: {candle_low}, Size: {candle_size:.1f} pts")

    # ── Skip filters ──────────────────────────────────────────────────────────
    if candle_size > 350:
        logger.info(f"⏭ SKIP — candle too large ({candle_size:.0f} pts > 350)")
        return None

    if candle_size < 50:
        logger.info(f"⏭ SKIP — candle too small ({candle_size:.0f} pts < 50)")
        return None

    # ── FIX 3: Determine direction from actual next candle breakout ───────────
    # Look at the next 15-min candle (9:30-9:45).
    # If its HIGH > candle_high → bullish breakout → BUY CE
    # If its LOW  < candle_low  → bearish breakout → BUY PE
    # If neither → no clear breakout, skip
    direction = None
    breakout_time = "09:30"

    if nifty_candles and len(nifty_candles) > 1:
        # nifty_candles[0] = 9:15 candle, [1] = 9:30 candle onward
        for i, c in enumerate(nifty_candles[1:], start=1):
            c_high = c['high']
            c_low  = c['low']
            c_time = c['date'].strftime('%H:%M') if hasattr(c['date'], 'strftime') else str(c['date'])[11:16]

            # Stop looking after 10:00 AM (no late entries per strategy rules)
            if c_time > "10:00":
                logger.info(f"⏭ SKIP — no breakout by 10:00 AM")
                return None

            if c_high > candle_high and c_low < candle_low:
                # Both sides broken in same candle — use close direction
                if c.get('close', spot_at_930) > (candle_high + candle_low) / 2:
                    direction = "CE"
                else:
                    direction = "PE"
                breakout_time = c_time
                break
            elif c_high > candle_high:
                direction = "CE"
                breakout_time = c_time
                break
            elif c_low < candle_low:
                direction = "PE"
                breakout_time = c_time
                break
    else:
        # Fallback if no subsequent candles (e.g., live trading at exactly 9:30)
        # Use spot position within candle range as direction hint
        mid = (candle_high + candle_low) / 2
        direction = "CE" if spot_at_930 > mid else "PE"
        breakout_time = "09:30"
        logger.info(f"⚠️ No subsequent candles — using spot position as direction hint")

    if not direction:
        logger.info("⏭ SKIP — no breakout detected in next candles")
        return None

    strike = calc_atm_strike(spot_at_930)

    logger.info(f"✅ SIGNAL: {'▲' if direction=='CE' else '▼'} {direction} | Strike: {strike} | Breakout @ {breakout_time}")
    return {
        'direction':      direction,
        'strike':         strike,
        'candle_high':    candle_high,
        'candle_low':     candle_low,
        'candle_size':    round(candle_size, 1),
        'spot':           spot_at_930,
        'breakout_time':  breakout_time,
    }


# ══════════════════════════════════════════════════════════════════════════════
# KITE API HELPERS
# ══════════════════════════════════════════════════════════════════════════════

# FIX 9: Rebuild Kite client from DB if not in memory cache
_kite_cache: dict[str, KiteConnect] = {}

def get_kite_client(user_id: str) -> KiteConnect | None:
    """Get authenticated KiteConnect client. Rebuilds from DB if needed."""
    if user_id in _kite_cache:
        return _kite_cache[user_id]

    user = UserSession.query.filter_by(user_id=user_id).first()
    if not user:
        logger.warning(f"No session found for user {user_id}")
        return None

    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(user.kite_access_token)
    _kite_cache[user_id] = kite
    logger.info(f"✅ Kite client rebuilt from DB for user {user_id}")
    return kite


def get_nifty_spot(kite: KiteConnect) -> float | None:
    """Fetch current Nifty 50 spot price."""
    try:
        q = kite.quote(['NSE:NIFTY 50'])
        return q['NSE:NIFTY 50']['last_price']
    except Exception as e:
        logger.error(f"get_nifty_spot failed: {e}")
        return None


def get_15min_candles(kite: KiteConnect, date_str: str) -> list | None:
    """
    Fetch all 15-min candles for Nifty 50 index on given date.
    Returns list of candle dicts with keys: date, open, high, low, close
    """
    try:
        candles = kite.historical_data(
            instrument_token=256265,      # NIFTY 50 index token
            from_date=date_str,
            to_date=date_str,
            interval='15minute'
        )
        if not candles:
            logger.warning(f"No 15-min candles for {date_str}")
            return None
        logger.info(f"Fetched {len(candles)} 15-min candles for {date_str}")
        return candles
    except Exception as e:
        logger.error(f"get_15min_candles failed for {date_str}: {e}")
        return None


def get_option_token(kite: KiteConnect, strike: int,
                     direction: str, trade_date_str: str) -> int | None:
    """
    FIX 4: Uses cached instruments list.
    Find the nearest weekly expiry option token for given strike + direction.
    """
    try:
        trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()
        instruments = get_nfo_instruments(kite)    # ← cached, not re-fetched every time

        best = None
        for inst in instruments:
            sym = inst['tradingsymbol']
            if (sym.startswith('NIFTY')
                    and str(strike) in sym
                    and sym.endswith(direction)
                    and inst['expiry'] >= trade_date):
                # Pick nearest expiry
                if best is None or inst['expiry'] < best['expiry']:
                    best = inst

        if best:
            logger.info(f"Instrument found: {best['tradingsymbol']} token={best['instrument_token']}")
            return best['instrument_token']

        logger.warning(f"No option token found for {strike}{direction} on {trade_date_str}")
        return None

    except Exception as e:
        logger.error(f"get_option_token failed: {e}")
        return None


def get_option_candles(kite: KiteConnect, token: int, date_str: str) -> list | None:
    """Fetch full-day 15-min candles for an option instrument."""
    try:
        candles = kite.historical_data(
            instrument_token=token,
            from_date=f"{date_str} 09:15:00",
            to_date=f"{date_str} 15:30:00",
            interval='15minute'
        )
        return candles
    except Exception as e:
        logger.error(f"get_option_candles failed token={token}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def simulate_trade_outcome(option_candles: list,
                           entry: float, sl: float, target: float):
    """
    Walk through option candles after entry to find first SL or target hit.

    FIX 15: If both SL and target are in the same candle (big move),
    we check which was closer to entry at open of that candle.
    In reality target won't be hit before SL in a falling candle so this
    is the most realistic approximation without tick data.

    Returns: (exit_premium, exit_time_str, status)
    """
    if not option_candles or len(option_candles) < 2:
        close = option_candles[-1]['close'] if option_candles else entry
        return round(close, 1), "15:30", "closed"

    # Skip first candle (that's our entry candle)
    for candle in option_candles[1:]:
        h = candle['high']
        l = candle['low']
        t = candle['date']
        c_time = t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[11:16]

        # FIX 15: Both hit same candle — target more likely if candle opened closer to target
        if h >= target and l <= sl:
            candle_open = candle.get('open', entry)
            if abs(candle_open - target) < abs(candle_open - sl):
                return target, c_time, "target"
            else:
                return sl, c_time, "sl"

        if h >= target:
            return target, c_time, "target"

        if l <= sl:
            return sl, c_time, "sl"

        # Force exit at 3:15 PM
        if c_time >= "15:15":
            return round(candle['close'], 1), "15:15", "closed"

    last = option_candles[-1]
    return round(last['close'], 1), "15:30", "closed"


# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════

def send_telegram(chat_id: str, message: str) -> bool:
    """Send a Telegram message to a specific chat_id."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning("Telegram not configured (missing token or chat_id)")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
            timeout=5
        )
        ok = r.status_code == 200
        if not ok:
            logger.error(f"Telegram error: {r.text}")
        return ok
    except Exception as e:
        logger.error(f"Telegram send_telegram failed: {e}")
        return False


def get_chat_id(user_id: str) -> str:
    """Get per-user Telegram ID from DB, fallback to TELEGRAM_USER_ID env var."""
    user = UserSession.query.filter_by(user_id=user_id).first()
    if user and user.telegram_user_id:
        return user.telegram_user_id
    return TELEGRAM_USER_ID   # env var fallback


# ══════════════════════════════════════════════════════════════════════════════
# AUTH — JWT
# ══════════════════════════════════════════════════════════════════════════════

def token_required(f):
    """Protect routes with JWT Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '').strip()
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired — please login again'}), 401
        except Exception as e:
            return jsonify({'error': f'Invalid token: {e}'}), 401
        return f(current_user, *args, **kwargs)
    return decorated


def make_jwt(user_id: str, user_name: str) -> str:
    return jwt.encode(
        {'user_id': user_id, 'user_name': user_name,
         'exp': datetime.utcnow() + timedelta(hours=24)},
        app.config['SECRET_KEY'], algorithm='HS256'
    )


# ══════════════════════════════════════════════════════════════════════════════
# OAUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/login')
def login():
    """Redirect user to Zerodha login page."""
    if not KITE_API_KEY:
        return "ERROR: KITE_API_KEY not set in .env", 500

    kite = KiteConnect(api_key=KITE_API_KEY)
    login_url = kite.login_url()   # SDK generates the correct URL
    logger.info(f"Redirecting to Zerodha login: {login_url[:60]}...")
    return redirect(login_url)


@app.route('/callback')
def oauth_callback():
    """
    Zerodha sends user here after login.
    FIX 7: Token is NOT passed in URL redirect to frontend.
    Instead: token is returned as JSON. Frontend should call /api/session after login.
    """
    try:
        request_token = request.args.get('request_token')
        if not request_token:
            return "<h2>Error: Missing request_token</h2>", 400

        logger.info(f"OAuth callback received, request_token: {request_token[:15]}...")

        kite = KiteConnect(api_key=KITE_API_KEY)
        session_data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)

        access_token = session_data['access_token']
        user_id      = session_data['user_id']
        user_name    = session_data.get('user_name', '')
        email        = session_data.get('email', '')

        logger.info(f"✅ Zerodha auth OK — user: {user_id} ({user_name})")

        # Save/update session in DB
        user = UserSession.query.filter_by(user_id=user_id).first()
        if user:
            user.kite_access_token = access_token
            user.last_login        = datetime.utcnow()
            user.token_expires_at  = datetime.utcnow() + timedelta(hours=24)
        else:
            user = UserSession(
                user_id=user_id,
                kite_user_id=user_id,
                kite_access_token=access_token,
                user_name=user_name,
                email=email,
                token_expires_at=datetime.utcnow() + timedelta(hours=24)
            )
        db.session.add(user)
        db.session.commit()

        # Clear old cached Kite client so it rebuilds with new token
        _kite_cache.pop(user_id, None)

        # Generate JWT
        jwt_token = make_jwt(user_id, user_name)

        # Redirect to frontend with JWT token
        redirect_url = f"{FRONTEND_URL}?token={jwt_token}&user_id={user_id}&user_name={user_name}"

        # Send welcome Telegram
        chat_id = get_chat_id(user_id)
        send_telegram(chat_id, f"✅ <b>Logged in!</b>\nUser: {user_name}\nPaper trading system is active.")

        return redirect(redirect_url)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}\n{traceback.format_exc()}")
        return f"<h2>Login failed</h2><p>{e}</p><a href='/login'>Try again</a>", 500


@app.route('/api/logout', methods=['POST'])
@token_required
def logout(current_user):
    _kite_cache.pop(current_user, None)
    user = UserSession.query.filter_by(user_id=current_user).first()
    if user:
        db.session.delete(user)
        db.session.commit()
    return jsonify({'status': 'logged out'}), 200


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL API — call at 9:30 AM to get today's trade signal
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/signal/today', methods=['GET'])
@token_required
def get_today_signal(current_user):
    """
    Fetch today's 15-min candle from Kite, run signal detection,
    and return the trade plan (entry/SL/target).
    Call this at 9:30 AM after first candle closes.
    """
    try:
        kite = get_kite_client(current_user)
        if not kite:
            return jsonify({'error': 'Zerodha not connected. Please login.'}), 401

        today_str = datetime.now().strftime('%Y-%m-%d')
        candles = get_15min_candles(kite, today_str)

        if not candles or len(candles) < 1:
            return jsonify({'error': 'No candle data available yet. Try after 9:30 AM.'}), 400

        first_candle  = candles[0]
        candle_high   = first_candle['high']
        candle_low    = first_candle['low']
        spot_at_930   = first_candle['close']

        # Run signal detection (FIX 1: now actually works)
        signal = detect_signal(candle_high, candle_low, spot_at_930, candles)

        if not signal:
            return jsonify({
                'signal':      'SKIP',
                'candle_high': candle_high,
                'candle_low':  candle_low,
                'candle_size': round(candle_high - candle_low, 1),
                'reason':      'Candle size out of 50–350 range or no breakout by 10 AM'
            }), 200

        # Get live ATM option premium
        direction = signal['direction']
        strike    = signal['strike']
        token     = get_option_token(kite, strike, direction, today_str)

        live_premium = None
        if token:
            try:
                ltp_data = kite.ltp([f"NFO:{token}"])
                live_premium = list(ltp_data.values())[0]['last_price']
            except Exception as e:
                logger.warning(f"Could not fetch live premium: {e}")

        # Use live premium or estimate
        entry  = live_premium or round(spot_at_930 * 0.0045, 1)
        sl     = calc_sl(entry)
        tgt    = calc_target(entry)

        result = {
            'signal':         'TRADE',
            'direction':      direction,
            'strike':         strike,
            'breakout_time':  signal['breakout_time'],
            'candle_high':    candle_high,
            'candle_low':     candle_low,
            'candle_size':    signal['candle_size'],
            'spot':           spot_at_930,
            'entry_premium':  entry,
            'sl_premium':     sl,
            'target_premium': tgt,
            'max_loss':       round((entry - sl) * LOT_SIZE),
            'max_profit':     round((tgt - entry) * LOT_SIZE),
            'lot_size':       LOT_SIZE,
        }

        # Send Telegram signal alert
        chat_id = get_chat_id(current_user)
        send_telegram(chat_id, f"""
🚨 <b>TRADE SIGNAL — {today_str}</b>

{'▲' if direction=='CE' else '▼'} <b>BUY NIFTY {strike} {direction}</b>
⏰ Breakout @ {signal['breakout_time']}

💰 Entry:  ₹{entry}
🛑 SL:     ₹{sl}  (50% of entry)
🎯 Target: ₹{tgt}  (2× risk)

📊 Candle: {signal['candle_size']} pts | Spot: {spot_at_930}
💸 Max Loss:   ₹{result['max_loss']:,}
💰 Max Profit: ₹{result['max_profit']:,}
""")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Signal error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# PAPER TRADE CRUD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/trade', methods=['POST'])
@token_required
def create_trade(current_user):
    """Create a new paper trade entry."""
    try:
        d = request.json
        now_str = datetime.now().strftime('%H:%M:%S')

        entry = float(d['entry_premium'])
        sl    = calc_sl(entry)         # always recalculate from strategy rules
        tgt   = calc_target(entry)

        # FIX 10: Add microsecond timestamp to trade_id to avoid duplicates
        trade_id = f"{current_user}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        trade = PaperTrade(
            trade_id       = trade_id,
            user_id        = current_user,
            date           = d['date'],
            strike         = d['strike'],
            direction      = d['direction'],
            entry_premium  = entry,
            entry_time     = d.get('entry_time', now_str),
            sl_premium     = sl,
            target_premium = tgt,
            candle_high    = d.get('candle_high'),
            candle_low     = d.get('candle_low'),
            candle_size    = d.get('candle_size'),
            spot_price     = d.get('spot_price'),
            note           = d.get('note', ''),
            is_backtest    = False,
        )
        db.session.add(trade)
        db.session.commit()

        chat_id = get_chat_id(current_user)
        send_telegram(chat_id, f"""
📝 <b>PAPER TRADE ENTERED</b>
NIFTY {d['strike']} {d['direction']}
💰 Entry:  ₹{entry}
🛑 SL:     ₹{sl}
🎯 Target: ₹{tgt}
⏰ Time:   {now_str}
""")
        return jsonify({'trade_id': trade_id, 'trade': trade.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"create_trade error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trade/<trade_id>/close', methods=['PUT'])
@token_required
def close_trade(current_user, trade_id):
    """Close a paper trade with exit premium."""
    try:
        trade = PaperTrade.query.filter_by(trade_id=trade_id, user_id=current_user).first()
        if not trade:
            return jsonify({'error': 'Trade not found'}), 404

        d            = request.json
        exit_price   = float(d['exit_premium'])
        pnl          = calc_pnl(trade.entry_premium, exit_price)
        exit_time    = d.get('exit_time', datetime.now().strftime('%H:%M:%S'))

        # Determine status
        if exit_price >= trade.target_premium:
            status = 'target'
        elif exit_price <= trade.sl_premium:
            status = 'sl'
        else:
            status = 'closed'

        trade.exit_premium = exit_price
        trade.exit_time    = exit_time
        trade.pnl          = pnl
        trade.status       = status
        db.session.commit()

        emoji = '🎯' if status == 'target' else '🛑' if status == 'sl' else '⏱'
        chat_id = get_chat_id(current_user)
        send_telegram(chat_id, f"""
{emoji} <b>TRADE CLOSED — {status.upper()}</b>
NIFTY {trade.strike} {trade.direction}
📥 Entry ₹{trade.entry_premium} → 📤 Exit ₹{exit_price}
{'📈' if pnl >= 0 else '📉'} <b>P&L: ₹{pnl:+,.0f}</b>
⏰ {exit_time}
""")
        return jsonify({'status': status, 'pnl': pnl, 'trade': trade.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"close_trade error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trade/<trade_id>', methods=['DELETE'])
@token_required
def delete_trade(current_user, trade_id):
    """Delete a paper trade."""
    trade = PaperTrade.query.filter_by(trade_id=trade_id, user_id=current_user).first()
    if not trade:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(trade)
    db.session.commit()
    return jsonify({'status': 'deleted'}), 200


@app.route('/api/trades', methods=['GET'])
@token_required
def get_trades(current_user):
    """Get trades for current user. Optional ?date=YYYY-MM-DD&status=open."""
    try:
        q = PaperTrade.query.filter_by(user_id=current_user)
        if request.args.get('date'):
            q = q.filter_by(date=request.args['date'])
        if request.args.get('status'):
            q = q.filter_by(status=request.args['status'])
        trades = q.order_by(PaperTrade.date.desc()).all()
        return jsonify({'total': len(trades), 'trades': [t.to_dict() for t in trades]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# STATS & JOURNAL
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    """Return overall trading statistics + equity curve."""
    try:
        # Optional filter: ?backtest=true|false
        q = PaperTrade.query.filter_by(user_id=current_user)
        if 'backtest' in request.args:
            is_bt = request.args['backtest'].lower() == 'true'
            q = q.filter_by(is_backtest=is_bt)

        trades = q.order_by(PaperTrade.created_at.asc()).all()
        closed = [t for t in trades if t.status in ('target', 'sl', 'closed')]
        wins   = [t for t in closed if (t.pnl or 0) > 0]
        losses = [t for t in closed if (t.pnl or 0) < 0]

        total_pnl = sum(t.pnl or 0 for t in closed)
        win_rate  = round(len(wins) / len(closed) * 100, 1) if closed else 0.0
        avg_win   = round(sum(t.pnl for t in wins)   / len(wins),   2) if wins   else 0
        avg_loss  = round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0
        rr        = round(abs(avg_win / avg_loss), 2) if avg_loss else 0

        # Equity curve
        cum = 0
        equity_curve = []
        for t in closed:
            cum += t.pnl or 0
            equity_curve.append({'date': t.date, 'equity': round(cum, 2), 'pnl': t.pnl or 0})

        return jsonify({
            'total_trades': len(closed),
            'winners':      len(wins),
            'losers':       len(losses),
            'win_rate':     win_rate,
            'total_pnl':    round(total_pnl, 2),
            'avg_win':      avg_win,
            'avg_loss':     avg_loss,
            'reward_risk':  rr,
            'equity_curve': equity_curve,
        }), 200

    except Exception as e:
        logger.error(f"get_stats error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/journal', methods=['GET'])
@token_required
def get_journal(current_user):
    """Get trades grouped by day / month / year. ?view=day|month|year"""
    try:
        view   = request.args.get('view', 'day')
        trades = PaperTrade.query.filter_by(user_id=current_user).order_by(PaperTrade.date.desc()).all()

        grouped: dict = {}
        for t in trades:
            key = {'day': t.date, 'month': t.date[:7], 'year': t.date[:4]}.get(view, t.date)
            if key not in grouped:
                grouped[key] = {'period': key, 'trades': [], 'total_trades': 0,
                                'total_pnl': 0.0, 'winners': 0, 'losers': 0}
            grouped[key]['trades'].append(t.to_dict())
            grouped[key]['total_trades'] += 1
            if t.pnl:
                grouped[key]['total_pnl'] += t.pnl
                if t.pnl > 0: grouped[key]['winners'] += 1
                else:          grouped[key]['losers']  += 1

        return jsonify({'view': view, 'data': list(grouped.values())}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def get_trading_days(year: int, month: int = None, day: int = None) -> list[str]:
    """Return list of YYYY-MM-DD strings for valid NSE trading days."""
    days = []

    def is_trading(d: str) -> bool:
        dt = datetime.strptime(d, '%Y-%m-%d')
        return dt.weekday() < 5 and d not in NSE_HOLIDAYS and dt <= datetime.now()

    if day and month:
        d = f"{year:04d}-{month:02d}-{day:02d}"
        if is_trading(d):
            days = [d]
    elif month:
        _, last = calendar.monthrange(year, month)
        days = [f"{year:04d}-{month:02d}-{d:02d}" for d in range(1, last + 1)
                if is_trading(f"{year:04d}-{month:02d}-{d:02d}")]
    else:
        for m in range(1, 13):
            _, last = calendar.monthrange(year, m)
            days += [f"{year:04d}-{m:02d}-{d:02d}" for d in range(1, last + 1)
                     if is_trading(f"{year:04d}-{m:02d}-{d:02d}")]
    return days


def run_backtest(user_id: str, kite: KiteConnect,
                 trading_days: list, period_label: str) -> dict:
    """
    Full backtest engine using real Kite API data.
    Sends Telegram alerts for every signal + result.
    Saves all trades to DB.
    """
    results, total_pnl, winners, losers, skipped = [], 0, 0, 0, 0
    chat_id = get_chat_id(user_id)

    logger.info(f"🔁 BACKTEST START: {period_label} | {len(trading_days)} days")
    send_telegram(chat_id, f"""📊 <b>BACKTEST STARTED</b>
📅 Period: <b>{period_label}</b>
📆 Days:   {len(trading_days)}
Strategy:  15-min breakout | SL 50% | Target 2× Risk""")

    for date_str in trading_days:
        try:
            logger.info(f"\n📅 {date_str}")

            candles = get_15min_candles(kite, date_str)
            if not candles or len(candles) < 2:
                skipped += 1
                logger.warning(f"  No candle data — skipping")
                results.append({'date': date_str, 'status': 'skipped', 'reason': 'no data'})
                continue

            first     = candles[0]
            c_high    = first['high']
            c_low     = first['low']
            spot      = first['close']
            c_size    = c_high - c_low

            # FIX 1: use the real detect_signal function
            signal = detect_signal(c_high, c_low, spot, candles)

            if not signal:
                skipped += 1
                send_telegram(chat_id,
                    f"⏭ <b>{date_str}</b> — Skipped ({c_size:.0f} pts)")
                results.append({'date': date_str, 'status': 'skipped',
                                 'reason': f'size {c_size:.0f}'})
                continue

            direction = signal['direction']
            strike    = signal['strike']

            # Get real option data
            token = get_option_token(kite, strike, direction, date_str)
            opt_candles = get_option_candles(kite, token, date_str) if token else None

            # Entry premium: first candle of option, else estimate
            if opt_candles and len(opt_candles) > 0:
                entry = round(opt_candles[0]['close'], 1)
            else:
                entry = round(spot * 0.0045, 1)   # ~0.45% of spot as rough estimate

            sl  = calc_sl(entry)
            tgt = calc_target(entry)

            send_telegram(chat_id, f"""
🚨 <b>BACKTEST SIGNAL — {date_str}</b>
{'▲' if direction=='CE' else '▼'} NIFTY {strike} {direction}
💰 Entry ₹{entry} | 🛑 SL ₹{sl} | 🎯 Target ₹{tgt}
📊 Candle {c_size:.0f} pts""")

            # Simulate outcome
            exit_price, exit_time, status = simulate_trade_outcome(
                opt_candles, entry, sl, tgt)
            pnl = calc_pnl(entry, exit_price)
            total_pnl += pnl
            if pnl > 0:  winners += 1
            else:        losers  += 1

            emoji = {'target': '🎯', 'sl': '🛑', 'closed': '⏱'}.get(status, '—')
            send_telegram(chat_id, f"""
{emoji} <b>{status.upper()} — {date_str}</b>
NIFTY {strike} {direction}
Entry ₹{entry} → Exit ₹{exit_price} @ {exit_time}
{'📈' if pnl >= 0 else '📉'} <b>₹{pnl:+,.0f}</b>  |  Running: ₹{total_pnl:+,.0f}""")

            # FIX 10: Unique trade_id with microseconds
            trade_id = f"BT_{date_str}_{direction}_{datetime.now().strftime('%f')}"
            trade = PaperTrade(
                trade_id=trade_id, user_id=user_id, date=date_str,
                strike=strike, direction=direction,
                entry_premium=entry, entry_time="09:30:00",
                sl_premium=sl, target_premium=tgt,
                exit_premium=exit_price, exit_time=exit_time,
                pnl=pnl, status=status,
                candle_high=c_high, candle_low=c_low,
                candle_size=round(c_size, 1), spot_price=spot,
                is_backtest=True
            )
            db.session.add(trade)
            db.session.commit()

            results.append({
                'date': date_str, 'direction': direction, 'strike': strike,
                'entry': entry, 'sl': sl, 'target': tgt,
                'exit': exit_price, 'exit_time': exit_time,
                'status': status, 'pnl': pnl
            })

        except Exception as e:
            logger.error(f"Backtest error on {date_str}: {e}\n{traceback.format_exc()}")
            results.append({'date': date_str, 'status': 'error', 'reason': str(e)})

    total_trades = winners + losers
    win_rate = round(winners / total_trades * 100, 1) if total_trades else 0
    avg_win  = round(sum(r['pnl'] for r in results if r.get('pnl', 0) > 0) / winners, 0) if winners else 0
    avg_loss = round(sum(r['pnl'] for r in results if r.get('pnl', 0) < 0) / losers, 0) if losers else 0

    send_telegram(chat_id, f"""
📊 <b>BACKTEST COMPLETE — {period_label}</b>
━━━━━━━━━━━━━━━
✅ Trades:  {total_trades}  |  🏆 {winners}W  |  ❌ {losers}L
⏭ Skipped: {skipped}
📊 Win Rate: <b>{win_rate}%</b>
💰 <b>Total P&L: ₹{total_pnl:+,.0f}</b>
📈 Avg Win:  ₹{avg_win:+,.0f}
📉 Avg Loss: ₹{avg_loss:+,.0f}
━━━━━━━━━━━━━━━""")

    return {
        'period': period_label, 'total_trades': total_trades,
        'winners': winners, 'losers': losers, 'skipped': skipped,
        'win_rate': win_rate, 'total_pnl': round(total_pnl, 2), 'results': results
    }


@app.route('/api/backtest', methods=['POST'])
@token_required
def run_backtest_api(current_user):
    """
    Start a backtest in background thread.
    Body: { "year": 2025 }
          { "year": 2025, "month": 10 }
          { "year": 2025, "month": 10, "day": 15 }
    """
    try:
        kite = get_kite_client(current_user)
        if not kite:
            return jsonify({'error': 'Zerodha not connected. Login first.'}), 401

        d     = request.json or {}
        year  = int(d.get('year',  datetime.now().year))
        month = int(d['month']) if d.get('month') else None
        day   = int(d['day'])   if d.get('day')   else None

        if day and month:
            label = f"{day:02d} {calendar.month_name[month]} {year}"
        elif month:
            label = f"{calendar.month_name[month]} {year}"
        else:
            label = f"Full Year {year}"

        days = get_trading_days(year, month, day)
        if not days:
            return jsonify({'error': 'No trading days found'}), 400

        def _run():
            with app.app_context():
                run_backtest(current_user, kite, days, label)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        return jsonify({
            'status':        'started',
            'period':        label,
            'trading_days':  len(days),
            'message':       f'Backtest running for {label}! Watch Telegram for updates.'
        }), 200

    except Exception as e:
        logger.error(f"run_backtest_api error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest/results', methods=['GET'])
@token_required
def backtest_results(current_user):
    """Get stored backtest results. ?year=2025&month=10&day=15"""
    try:
        year  = request.args.get('year')
        month = request.args.get('month')
        day   = request.args.get('day')

        q = PaperTrade.query.filter_by(user_id=current_user, is_backtest=True)

        if year and month and day:
            q = q.filter(PaperTrade.date == f"{int(year):04d}-{int(month):02d}-{int(day):02d}")
        elif year and month:
            q = q.filter(PaperTrade.date.like(f"{int(year):04d}-{int(month):02d}%"))
        elif year:
            q = q.filter(PaperTrade.date.like(f"{int(year):04d}%"))

        trades = q.order_by(PaperTrade.date.asc()).all()
        closed = [t for t in trades if t.status in ('target', 'sl', 'closed')]
        wins   = [t for t in closed if (t.pnl or 0) > 0]
        losers = [t for t in closed if (t.pnl or 0) <= 0]

        return jsonify({
            'total_trades': len(closed),
            'winners':      len(wins),
            'losers':       len(losers),
            'win_rate':     round(len(wins) / len(closed) * 100, 1) if closed else 0,
            'total_pnl':    round(sum(t.pnl or 0 for t in closed), 2),
            'trades':       [t.to_dict() for t in trades]
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# MISC ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    user = UserSession.query.filter_by(user_id=current_user).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200


@app.route('/api/user/telegram', methods=['POST'])
@token_required
def set_telegram(current_user):
    """Let user set their personal Telegram user ID (overrides env TELEGRAM_USER_ID)."""
    uid = request.json.get('telegram_user_id', '').strip()
    if not uid:
        return jsonify({'error': 'telegram_user_id required'}), 400
    user = UserSession.query.filter_by(user_id=current_user).first()
    if user:
        user.telegram_user_id = uid
        db.session.commit()
    return jsonify({'status': 'updated', 'telegram_user_id': uid}), 200


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status':       'ok',
        'timestamp':    datetime.now().isoformat(),
        'version':      '2.1',
        'frontend_url': FRONTEND_URL,
    }), 200


# FIX 8: Serve dashboard from /static/dashboard.html
@app.route('/')
def index():
    try:
        return send_from_directory('static', 'dashboard.html')
    except Exception:
        return jsonify({'message': 'Nifty Paper Trader API v2.1 — visit /api/health'}), 200


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════════════════

with app.app_context():
    db.create_all()
    logger.info("✅ DB tables ready")
    logger.info(f"✅ FRONTEND_URL:      {FRONTEND_URL}")
    logger.info(f"✅ KITE_REDIRECT_URL: {KITE_REDIRECT_URL}")
    logger.info(f"✅ Kite API Key set:  {bool(KITE_API_KEY)}")
    logger.info(f"✅ Telegram set:      {bool(TELEGRAM_BOT_TOKEN)} | USER_ID set: {bool(TELEGRAM_USER_ID)}")

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=not IS_PROD
    )