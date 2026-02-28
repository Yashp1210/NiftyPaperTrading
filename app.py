"""
Nifty 50 Paper Trading System - Flask Backend
Automated signal detection + paper trade journal + Telegram alerts
Author: Yash Patel | GitHub: Yashp1210
"""

from flask import Flask, request, jsonify, send_from_directory
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

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///paper_trades.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-prod')

CORS(app)
db = SQLAlchemy(app)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8772922884:AAG4JqS9TiDJL-aDYZM-dKdXvGdfFOZycqI')
TELEGRAM_USER_ID = os.getenv('TELEGRAM_USER_ID', '653550541')
KITE_API_KEY = os.getenv('KITE_API_KEY', '')
KITE_API_SECRET = os.getenv('KITE_API_SECRET', '')
KITE_ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN', '')

# Global state
current_signal = None
active_trade = None
kite = None

# ==================== DATABASE MODELS ====================

class PaperTrade(db.Model):
    """SQLAlchemy model for paper trades"""
    __tablename__ = 'paper_trades'
    
    trade_id = db.Column(db.String(50), primary_key=True)
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
            # Extract token from "Bearer <token>"
            token = token.split(' ')[1] if ' ' in token else token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['user']
        except Exception as e:
            logger.error(f"Token error: {e}")
            return jsonify({'error': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# ==================== KITE API FUNCTIONS ====================

def init_kite():
    """Initialize Kite API connection"""
    global kite
    try:
        if KITE_ACCESS_TOKEN:
            kite = KiteConnect(api_key=KITE_API_KEY)
            kite.set_access_token(KITE_ACCESS_TOKEN)
            logger.info("Kite API initialized successfully")
            return True
        else:
            logger.warning("Kite access token not set")
            return False
    except Exception as e:
        logger.error(f"Failed to initialize Kite: {e}")
        return False

def get_nifty_spot():
    """Fetch current Nifty 50 spot price"""
    try:
        if not kite:
            return None
        quote = kite.quote(instrument_tokens=[256265])  # NIFTY 50 token
        spot = quote['256265']['last_price']
        return spot
    except Exception as e:
        logger.error(f"Error fetching Nifty spot: {e}")
        return None

def get_first_15min_candle(date_str):
    """Fetch 9:15-9:30 AM candle data"""
    try:
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

def get_atm_premium(strike, direction):
    """Fetch ATM premium from Kite API"""
    try:
        if not kite:
            return None
        
        # NFO NIFTY weekly option tokens (example - will vary)
        # For now, returning placeholder
        # In production, you'd query the actual option chain
        return None
    except Exception as e:
        logger.error(f"Error fetching premium: {e}")
        return None

# ==================== SIGNAL DETECTION ====================

def detect_signal(candle_high, candle_low, spot_price):
    """
    Detect breakout signal from 9:15-9:30 candle
    Returns: 'CE' (bullish) or 'PE' (bearish) or None
    """
    candle_size = candle_high - candle_low
    
    # Skip conditions
    if candle_size > 350 or candle_size < 50:
        logger.info(f"Candle skipped - size: {candle_size}")
        return None
    
    # Signal detection (simplified for paper trading)
    # In live, you'd check if price broke above high or below low
    return None

def send_telegram_alert(message):
    """Send alert to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_USER_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logger.info(f"Telegram alert sent: {message[:50]}")
            return True
        else:
            logger.error(f"Telegram error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

# ==================== API ROUTES ====================

@app.route('/api/login', methods=['POST'])
def login():
    """
    Login endpoint - returns JWT token
    Body: { "api_key": "...", "api_secret": "..." }
    """
    try:
        data = request.json
        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')
        
        # Simple validation (in production, verify against actual Zerodha account)
        if not api_key or not api_secret:
            return jsonify({'error': 'API key and secret required'}), 400
        
        # Generate JWT token (valid for 24 hours)
        token = jwt.encode({
            'user': api_key,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'expires_in': 86400
        }), 200
    
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signal', methods=['GET'])
@token_required
def get_signal(current_user):
    """
    Get current signal
    Returns: { signal: 'CE'/'PE'/null, candle_high, candle_low, spot, timestamp }
    """
    try:
        spot = get_nifty_spot()
        today = datetime.now().strftime('%Y-%m-%d')
        candle = get_first_15min_candle(today)
        
        if candle and spot:
            signal = detect_signal(candle['high'], candle['low'], spot)
            return jsonify({
                'signal': signal,
                'candle_high': candle['high'],
                'candle_low': candle['low'],
                'spot': spot,
                'timestamp': datetime.now().isoformat(),
                'atm_strike': get_atm_strike(spot)
            }), 200
        else:
            return jsonify({'error': 'Unable to fetch signal data'}), 500
    
    except Exception as e:
        logger.error(f"Signal error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trade', methods=['POST'])
@token_required
def create_trade(current_user):
    """
    Create new paper trade entry
    Body: {
        date, strike, direction, entry_premium, sl_premium, target_premium,
        candle_high, candle_low, spot_price
    }
    """
    try:
        data = request.json
        
        # Generate trade ID
        trade_id = f"{data['date']}-{data['strike']}-{data['direction']}-{datetime.now().timestamp()}"
        
        new_trade = PaperTrade(
            trade_id=trade_id,
            date=data['date'],
            strike=data['strike'],
            direction=data['direction'],
            entry_premium=data['entry_premium'],
            entry_time=datetime.now().strftime('%H:%M:%S'),
            sl_premium=data['sl_premium'],
            target_premium=data['target_premium'],
            candle_high=data.get('candle_high'),
            candle_low=data.get('candle_low'),
            spot_price=data.get('spot_price'),
            status='open'
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
        send_telegram_alert(msg)
        
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
    """
    Close a trade with exit premium
    Body: { exit_premium }
    """
    try:
        trade = PaperTrade.query.filter_by(trade_id=trade_id).first()
        
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
        send_telegram_alert(msg)
        
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
    """Get all trades with optional filters"""
    try:
        date_filter = request.args.get('date')
        month_filter = request.args.get('month')
        status_filter = request.args.get('status')
        
        query = PaperTrade.query
        
        if date_filter:
            query = query.filter_by(date=date_filter)
        
        if month_filter:
            query = query.filter(PaperTrade.date.like(f'{month_filter}%'))
        
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
        trades = PaperTrade.query.order_by(PaperTrade.date.desc()).all()
        
        grouped = {}
        
        for trade in trades:
            if view == 'day':
                key = trade.date
            elif view == 'month':
                key = trade.date[:7]  # YYYY-MM
            else:  # year
                key = trade.date[:4]  # YYYY
            
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
        trades = PaperTrade.query.all()
        
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
                'pnl': trade.pnl
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
        'telegram_connected': TELEGRAM_BOT_TOKEN != '',
        'kite_connected': kite is not None
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

# ==================== SCHEDULED TASKS ====================

def scheduled_signal_check():
    """Run signal detection at 9:30 AM IST"""
    pass  # Implement if needed for automated checks

def run_scheduler():
    """Run scheduler in background thread"""
    while True:
        schedule.run_pending()
        threading.Event().wait(1)

# ==================== INITIALIZATION ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_kite()

        # Start scheduler in background
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        # Run Flask app
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('PORT', 5000)),
            debug=os.getenv('FLASK_ENV', 'production') == 'development'
        )