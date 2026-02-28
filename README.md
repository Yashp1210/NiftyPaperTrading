# Nifty Paper Trading System - OAuth 2.0 Edition

A secure, automated paper trading journal for managing options trades with Zerodha OAuth 2.0 authentication, real-time alerts, and comprehensive analytics.

---

## 📋 What's Included

✅ **Zerodha OAuth 2.0** - Secure login without sharing credentials  
✅ **Flask Backend** - Production-ready API with JWT authentication  
✅ **Web Dashboard** - Real-time trade management interface  
✅ **SQLite Database** - Persistent trade history and analytics  
✅ **Telegram Bot** - Real-time trade alerts and notifications  
✅ **Multi-User Support** - Each user has their own trades  
✅ **Cloud Ready** - Deploy on Render in minutes  

---

## 🚀 QUICK START (5 Minutes)

### Step 1: Create Zerodha OAuth App

1. Go to https://kite.trade/apps
2. Click **"Create New App"** (top right)
3. Fill the form:
   ```
   App Name: NiftyPaperTrading
   App Type: Trade
   Redirect URL: http://localhost:5000/callback
   Postback URL: (leave blank)
   ```
4. Click **"Create App"**
5. You'll see **API Key** and **API Secret** → Copy both

### Step 2: Setup Local Environment

#### On Windows:
```bash
# 1. Extract the zip file
# 2. Open Command Prompt in the folder
# 3. Run:
run.bat
```

#### On Mac/Linux:
```bash
# 1. Extract the zip file
# 2. Open Terminal in the folder
# 3. Run:
chmod +x run.sh
./run.sh
```

### Step 3: Configure Credentials

1. Open `.env` file in notepad
2. Find these lines:
   ```env
   KITE_API_KEY=your_api_key_here
   KITE_API_SECRET=your_api_secret_here
   ```
3. Replace with values from Step 1
4. Save and close

### Step 4: Start Trading!

1. Browser opens: http://localhost:5000
2. Click **"Connect Zerodha Account"** button
3. Login to your Zerodha account (on Zerodha page)
4. You'll be redirected back to dashboard ✅
5. Start creating paper trades!

---

## 🔐 How It Works (OAuth 2.0)

### Traditional Login (OLD) ❌
```
You enter API Key + Secret → App stores them → Risk if database hacked
```

### Zerodha OAuth (NEW) ✅
```
You click "Connect" → Zerodha page (secure) → You approve access
→ Zerodha gives encrypted token → Dashboard never sees your password
```

**You never give your API key/secret to the dashboard - Zerodha does that securely!**

---

## 📝 Environment Setup

Create `.env` file in root directory with:

```env
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=any-random-string-here
PORT=5000

# Zerodha OAuth (from kite.trade/apps)
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_REDIRECT_URL=http://localhost:5000/callback

# Telegram (Optional - for trade alerts)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_user_id_here

# Database
DATABASE_URL=sqlite:///paper_trades.db
```

---

## 🌐 Deploy on Render (Production)

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Zerodha OAuth app"
git remote add origin https://github.com/YOUR_USERNAME/NiftyPaperTrading.git
git branch -M main
git push -u origin main
```

### Step 2: Create Render Web Service

1. Go to https://render.com
2. Sign up with GitHub
3. Click **"New +"** → **"Web Service"**
4. Select your repository
5. Configure:
   ```
   Name: nifty-paper-trading
   Environment: Python
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   ```

### Step 3: Add Environment Variables

In Render dashboard → **Settings** → **Environment**:

```
FLASK_ENV=production
SECRET_KEY=(Render generates this automatically)
KITE_API_KEY=your_value
KITE_API_SECRET=your_value
KITE_REDIRECT_URL=https://nifty-paper-trading.onrender.com/callback
TELEGRAM_BOT_TOKEN=your_value
TELEGRAM_USER_ID=your_value
```

### Step 4: Update Zerodha OAuth App

1. Go to https://kite.trade/apps
2. Edit your app
3. Update **Redirect URL**:
   ```
   https://nifty-paper-trading.onrender.com/callback
   ```
4. Save

### Step 5: Deploy & Test

```bash
# In Render dashboard, click Deploy
# Wait 2-3 minutes
# Visit: https://nifty-paper-trading.onrender.com
```

---

## 📡 API Endpoints

### Authentication
```
GET    /login                   # Initiate Zerodha OAuth
GET    /callback                # OAuth callback handler
POST   /api/logout              # Logout (requires JWT token)
```

### User
```
GET    /api/user/profile        # Get current user info
```

### Trades
```
POST   /api/trade               # Create new trade
GET    /api/trades              # List user's trades
PUT    /api/trade/<id>/close    # Close a trade
GET    /api/journal             # Get journal (grouped by day/month/year)
GET    /api/stats               # Get statistics
```

### System
```
GET    /api/health              # Health check
```

---

## 💬 Telegram Alerts Setup (Optional)

### Create Telegram Bot

1. Search for **@BotFather** on Telegram
2. Send `/newbot`
3. Follow instructions to create bot
4. Copy bot token

### Get Your User ID

1. Search for **@userinfobot** on Telegram
2. Send `/start`
3. Copy your user ID

### Add to .env

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefghijklmnopqrst
TELEGRAM_USER_ID=987654321
```

### Test It

1. Start app: `python app.py`
2. Create a trade
3. Check Telegram for alert message ✅

---

## 📊 Features Explained

### Dashboard Tab
- See your current active trades
- Real-time P&L tracking
- Quick access to close trades

### New Trade Tab
- **Date:** Trade date (today's date auto-filled)
- **Strike:** Nifty strike price (24000, 24050, etc.)
- **Direction:** CE (Call) = bullish, PE (Put) = bearish
- **Entry Premium:** How much you paid for the option (₹)
- **SL Premium:** Stop loss level (auto-calculated)
- **Target Premium:** Take profit level (auto-calculated)
- Max Loss/Profit shows risk-reward ratio

### Journal Tab
- View all past trades
- Filter by date/month/year
- Shows P&L for each trade
- Status: Open, Closed, Target Hit, Stop Loss

### Statistics Tab
- **Total Trades:** Number of trades taken
- **Win Rate:** % of profitable trades
- **Total P&L:** Cumulative profit/loss
- **Winners:** Number of winning trades
- **Equity Curve:** Graph showing account growth

---

## 🔒 Security Best Practices

✅ **Never share your .env file** - It contains API keys  
✅ **Use HTTPS** - Always use https:// for production URLs  
✅ **Rotate JWT tokens** - They expire after 24 hours  
✅ **Keep API keys secure** - Don't share Zerodha credentials  
✅ **Encrypt database** - Optional but recommended for live trading  

---

## 🐛 Troubleshooting

### "Cannot connect to Zerodha"
- Check internet connection
- Verify API key/secret in .env
- Ensure kite.trade/apps redirect URL matches

### "Login redirects to Zerodha but doesn't come back"
- Check KITE_REDIRECT_URL in .env
- Must match exactly: `http://localhost:5000/callback`
- Check Zerodha app settings: https://kite.trade/apps

### "Telegram alerts not received"
- Verify bot token is correct
- Make sure you sent `/start` to the bot first
- Check user ID is correct
- Telegram might be blocked in your region

### "Port 5000 already in use"
- Change PORT in .env to 5001
- Or kill process: `lsof -ti:5000 | xargs kill`

### "Database is locked"
- Close other instances of the app
- Delete `paper_trades.db` to reset
- Restart Flask

---

## 📈 Trading Workflow

### 9:15 AM (Market Open)
1. Start app: `python app.py`
2. Click "Connect Zerodha Account"
3. Login to Zerodha (you see 9:15-9:30 candle signal)

### 9:30 AM (After Candle Closes)
1. Go to "New Trade" tab
2. Check if signal suggests CE (bullish) or PE (bearish)
3. Enter strike, direction, entry premium
4. SL and Target auto-calculate
5. Click "Create Trade" → Telegram alert sent

### During Trading Hours
1. Monitor trade in "Active Trades"
2. Watch live premium price
3. Update exit premium when ready

### 3:15 PM (Close)
1. Check exit premium price
2. Click "Close Trade"
3. Enter final premium
4. Telegram alert shows P&L ✅

### After Hours
1. Go to "Journal" tab → see all trades
2. Go to "Stats" tab → check win rate and P&L
3. Log notes in trading diary

---

## 📚 Example Trade

```
Date: 2026-02-28
Strike: 24000
Direction: CE (Call - Bullish)
Entry Premium: ₹150
SL Premium: ₹75 (50% of entry)
Target Premium: ₹300 (2:1 RR)

Max Loss: (150 - 75) × 50 qty = ₹3,750
Max Profit: (300 - 150) × 50 qty = ₹7,500

Later at 3:15 PM:
Exit Premium: ₹280
P&L: (280 - 150) × 50 = ₹6,500 ✅ WINNER
```

---

## 🎯 Next Steps

1. **Test Locally First**
   - Run `python app.py`
   - Create 10-20 paper trades
   - Verify win rate stabilizes

2. **Validate Strategy**
   - Track stats for 2-4 weeks
   - Win rate should be > 55%
   - Check equity curve is growing

3. **Go Live (Optional)**
   - Buy Kite subscription (₹500/month)
   - Start with small capital
   - Risk only 1-2% per trade

---

## 📞 Support & Resources

- **Kite API Docs:** https://kite.trade/docs/connect/v3/
- **Render Deployment:** https://render.com/docs
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **Flask Documentation:** https://flask.palletsprojects.com/

---

## 📝 License

For personal use only. Redistribution prohibited without permission.

**Disclaimer:** This is a paper trading tool for learning only. Always validate strategies before risking real money.

---

## 🎯 Version History

- **v2.0** (Feb 2026) - Zerodha OAuth 2.0, Multi-user support
- **v1.0** (Feb 2026) - Initial release with manual API key login

---

**Developed by Yash Patel**  
**GitHub:** Yashp1210  
**Created:** Feb 28, 2026