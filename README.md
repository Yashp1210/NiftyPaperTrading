# 🚀 Nifty Paper Trading System

Automated paper trading journal for **Nifty 50 Weekly Options** using the **9:15-9:30 AM First Candle Breakout Strategy**.

---

## 📋 What's Included

✅ **Flask Backend** - Kite API integration + signal detection + Telegram alerts + JWT auth  
✅ **React Frontend** - Dashboard, journal (day/month/year), stats, trade entry  
✅ **SQLite Database** - Persistent paper trade journal  
✅ **Telegram Bot** - Entry/exit/SL/target alerts  
✅ **JWT Authentication** - Secure API endpoints  
✅ **Production Ready** - Deploy on Render in 5 minutes  

---

## 🔧 QUICK START (Local Development)

### 1. Clone & Setup

```bash
# Extract the zip file
cd NiftyPaperTrading

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy .env template
cp .env.example .env

# Edit .env with your credentials
# (instructions below)
```

### 3. Run Locally

```bash
# Start Flask backend (runs on http://localhost:5000)
python app.py
```

The app will:
- ✅ Create SQLite database automatically
- ✅ Start Flask server on `localhost:5000`
- ✅ Initialize Kite API connection (if tokens provided)
- ✅ Listen for API calls from frontend

---

## 🔑 Getting Your Credentials

### A. Telegram Bot Token (Already Done ✅)

```
Token: 8772922884:AAG4JqS9TiDJL-aDYZM-dKdXvGdfFOZycqI
User ID: 653550541
```

These are already in the code!

### B. Zerodha Kite API Key (BEFORE BUYING ₹500 SUBSCRIPTION)

1. Go to https://kite.trade/apps
2. Click "Create New App"
3. Fill form:
   - **App Name:** `NiftyPaperTrading`
   - **App Type:** `Trade`
   - **Redirect URL:** `http://localhost:5000/callback` (local testing)
                       OR `https://nifty-paper-trading.onrender.com/callback` (after Render deployment)
   - **Postback URL:** Leave empty or same as redirect

4. You'll get:
   - `API_KEY` (e.g., `h8pxyz12`)
   - `API_SECRET` (e.g., `abcd1234efgh5678`)

5. Add these to your `.env` file

### C. Kite Access Token (After Buying Subscription)

1. Complete OAuth flow via Kite app
2. Get `ACCESS_TOKEN` from the response
3. Add to `.env`

---

## 📝 Setting Up .env File

Create `.env` in the root directory:

```env
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-super-secret-key-here
PORT=5000

# Telegram (Already configured)
TELEGRAM_BOT_TOKEN=8772922884:AAG4JqS9TiDJL-aDYZM-dKdXvGdfFOZycqI
TELEGRAM_USER_ID=653550541

# Zerodha Kite API (Get from https://kite.trade/apps)
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_after_oauth

# Database
DATABASE_URL=sqlite:///paper_trades.db

# JWT Settings
JWT_EXPIRY_HOURS=24
```

---

## 🌐 Deploying on Render (FREE)

### Step 1: Create GitHub Repository

```bash
# Initialize git
git init
git add .
git commit -m "Initial commit - Nifty paper trading system"

# Create repo on GitHub
# Push to GitHub
git remote add origin https://github.com/Yashp1210/NiftyPaperTrading.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to https://render.com (sign up with GitHub)
2. Click "New +" → "Web Service"
3. Connect your GitHub repo (`NiftyPaperTrading`)
4. Configure:
   - **Name:** `nifty-paper-trading`
   - **Environment:** `Python`
   - **Runtime:** `3.11`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Click "Create Web Service"

### Step 3: Add Environment Variables on Render

After deployment, go to your service dashboard:
1. Click "Settings" → "Environment"
2. Add these variables:

```
TELEGRAM_BOT_TOKEN=8772922884:AAG4JqS9TiDJL-aDYZM-dKdXvGdfFOZycqI
TELEGRAM_USER_ID=653550541
KITE_API_KEY=<your_api_key>
KITE_API_SECRET=<your_api_secret>
KITE_ACCESS_TOKEN=<your_access_token>
SECRET_KEY=<generate_a_random_string>
FLASK_ENV=production
```

3. Click "Save"

Your app will restart and be live at:
```
https://nifty-paper-trading.onrender.com
```

### Step 4: Update Kite Redirect URL

Go back to https://kite.trade/apps and edit your app:
- **Redirect URL:** `https://nifty-paper-trading.onrender.com/callback`
- Save

---

## 📡 API ENDPOINTS

All endpoints require JWT token in header:
```
Authorization: Bearer <your_token>
```

### Authentication
```
POST /api/login
Body: { "api_key": "...", "api_secret": "..." }
Response: { "token": "...", "expires_in": 86400 }
```

### Signals
```
GET /api/signal
Response: { 
  "signal": "CE"/"PE"/null,
  "candle_high": 24150,
  "candle_low": 24050,
  "spot": 24100,
  "atm_strike": 24100,
  "timestamp": "2026-02-28T09:30:00"
}
```

### Trades
```
POST /api/trade
Body: {
  "date": "2026-02-28",
  "strike": 24100,
  "direction": "CE",
  "entry_premium": 150,
  "sl_premium": 75,
  "target_premium": 300,
  "candle_high": 24150,
  "candle_low": 24050,
  "spot_price": 24100
}

GET /api/trades?date=2026-02-28&status=open
Response: { "total": 5, "trades": [...] }

PUT /api/trade/<trade_id>/close
Body: { "exit_premium": 250 }
```

### Journal
```
GET /api/journal?view=day
GET /api/journal?view=month
GET /api/journal?view=year
```

### Statistics
```
GET /api/stats
Response: {
  "total_trades": 50,
  "closed_trades": 45,
  "winners": 28,
  "losers": 17,
  "win_rate": 62.22,
  "total_pnl": 45000,
  "avg_win": 2500,
  "avg_loss": -1500,
  "equity_curve": [...]
}
```

---

## 🔒 Security Features

✅ **JWT Authentication** - All endpoints protected  
✅ **API Key Encryption** - Stored securely in .env  
✅ **CORS Enabled** - Frontend can access backend  
✅ **Rate Limiting** - Can be added later  
✅ **HTTPS** - Render provides SSL certificate  

---

## 📊 Database Schema

```sql
CREATE TABLE paper_trades (
  trade_id TEXT PRIMARY KEY,
  date TEXT,
  strike INTEGER,
  direction TEXT,           -- CE or PE
  entry_premium REAL,
  entry_time TEXT,
  sl_premium REAL,
  target_premium REAL,
  exit_premium REAL,
  exit_time TEXT,
  pnl REAL,
  status TEXT,              -- open, closed, target, sl
  candle_high REAL,
  candle_low REAL,
  spot_price REAL,
  created_at TIMESTAMP
);
```

---

## 🚀 WORKFLOW

### Daily Trading Routine (Paper Trading Phase)

1. **9:30 AM IST** - App ready (open browser)
2. **Enter Login** - Use Kite API key + secret (from https://kite.trade/apps)
3. **Check Signal** - Dashboard shows 9:15-9:30 candle breakout
4. **Create Trade** - Click "New Trade" → Fill entry/SL/target
5. **Get Alert** - Telegram bot sends "✅ TRADE ENTERED" message
6. **Monitor** - Update live LTP in dashboard
7. **Close Trade** - Click "Close Trade" → Enter exit premium
8. **Get Alert** - Telegram bot sends "✅ TARGET HIT" or "❌ STOP LOSS"
9. **Repeat** - Journal auto-updates with P&L

---

## 📈 NEXT STEPS

### Phase 1 (NOW) - Paper Trading
- ✅ Run code locally or on Render
- ✅ Log 20+ trades manually
- Track stats (win rate, avg P&L)

### Phase 2 (NEXT) - Semi-Automation
- Auto-fetch 9:15-9:30 candle via Kite API
- Auto-calculate signal + notify on Telegram
- Still manually enter/exit trades

### Phase 3 (FUTURE) - Full Automation
- Auto-place orders via Kite API
- GTT for SL + target
- Auto square-off at 3:15 PM
- Requires: Static IP or GTT workaround

---

## 🐛 TROUBLESHOOTING

### "Cannot connect to Kite API"
- Check KITE_ACCESS_TOKEN in .env
- Verify ₹500 subscription is active
- Check if token has expired (need to refresh)

### "Telegram alerts not received"
- Verify TELEGRAM_BOT_TOKEN is correct
- Verify TELEGRAM_USER_ID is correct
- Send `/start` to @nifty_paper_trader_bot

### "Database locked error"
- Close other instances of the app
- Delete `paper_trades.db` and restart

### "Port 5000 already in use"
- Change `PORT=5000` to `PORT=5001` in .env
- Or kill the process using port 5000

---

## 📞 SUPPORT

- **Kite API Docs:** https://kite.trade/docs/connect/v3/
- **Render Docs:** https://render.com/docs
- **Telegram Bot API:** https://core.telegram.org/bots/api

---

## 📄 LICENSE

Personal use. Not for distribution.

---

## 🎯 GOALS

✅ Validate Nifty 50 breakout strategy with paper trades  
✅ Track day/month/year P&L  
✅ Get Telegram alerts  
✅ Deploy on free Render VPS  
✅ Automate when ready to trade live  

---

**Built by Yash Patel | GitHub: Yashp1210**  
**Start date:** Feb 28, 2026
