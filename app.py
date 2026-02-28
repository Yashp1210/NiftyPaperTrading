"""
Nifty 50 Paper Trading System - Flask Backend
Automated signal detection + paper trade journal + Telegram alerts
Zerodha OAuth 2.0 Compatible
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

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        params = {
            'v': '3',
            'client_id': KITE_API_KEY,
            'redirect_uri': KITE_REDIRECT_URL
        }
        login_url = f"{KITE_LOGIN_URL}?{urlencode(params)}"
        return redirect(login_url)
    except Exception as e:
        logger.error(f"Login redirect error: {e}")
        return jsonify({'error': 'Login failed'}), 400

@app.route('/callback', methods=['GET'])
def oauth_callback():
    """Handle Zerodha OAuth callback"""
    try:
        request_token = request.args.get('request_token')

        if not request_token:
            return jsonify({'error': 'Missing request token'}), 400

        # Exchange request token for access token
        checksum = f"{KITE_API_KEY}{request_token}{KITE_API_SECRET}"
        import hashlib
        checksum = hashlib.sha256(checksum.encode()).hexdigest()

        payload = {
            'api_key': KITE_API_KEY,
            'request_token': request_token,
            'checksum': checksum
        }

        response = requests.post(f"{KITE_TOKEN_URL}", data=payload)

        if response.status_code != 200:
            return jsonify({'error': 'Token exchange failed'}), 400

        data = response.json()

        if not data.get('data'):
            return jsonify({'error': 'Invalid token response'}), 400

        access_token = data['data']['access_token']
        user_id = data['data']['user_id']
        user_name = data['data'].get('user_name', '')
        email = data['data'].get('email', '')

        # Store/update user session
        user_session = UserSession.query.filter_by(user_id=user_id).first()

        if user_session:
            user_session.kite_access_token = access_token
            user_session.last_login = datetime.utcnow()
        else:
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

        # Generate JWT token
        jwt_token = jwt.encode({
            'user_id': user_id,
            'user_name': user_name,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')

        # Redirect to frontend with token
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        return redirect(f"{frontend_url}?token={jwt_token}&user_id={user_id}")

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return jsonify({'error': 'Callback processing failed'}), 500

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

def get_atm_strike(spot):
    """Calculate ATM strike"""
    return round(spot / 50) * 50

def detect_signal(candle_high, candle_low, spot_price):
    """Detect breakout signal from 9:15-9:30 candle"""
    candle_size = candle_high - candle_low

    if candle_size > 350 or candle_size < 50:
        logger.info(f"Candle skipped - size: {candle_size}")
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

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0',
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")

        # Run Flask app
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('PORT', 5000)),
            debug=os.getenv('FLASK_ENV', 'production') == 'development'
        )