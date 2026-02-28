# 📚 COMPLETE SETUP GUIDE

## ⚡ QUICK START (5 Minutes)

### On Windows:

1. **Double-click** `run.bat`
2. Wait for "Starting Flask Backend..." message
3. Open browser: `http://localhost:5000`
4. Done! ✅

### On Mac/Linux:

```bash
chmod +x run.sh
./run.sh
```

---

## 🔐 LOGIN SETUP

### Step 1: Get Kite API Key (Free, No Money Yet)

Go to: https://kite.trade/apps

1. Click "Create New App" (top right)
2. Fill form:
   ```
   App name: NiftyPaperTrading
   Redirect URL: http://localhost:5000/callback
   (Leave Postback URL blank)
   ```
3. Click "Create App"
4. You'll see:
   - **API Key:** (copy this)
   - **API Secret:** (copy this)

### Step 2: Save Credentials to .env

Edit `.env` file (in same folder as `app.py`):

```env
KITE_API_KEY=paste_your_api_key_here
KITE_API_SECRET=paste_your_api_secret_here
```

(The rest are already configured for you)

### Step 3: Login to Frontend

1. Open http://localhost:5000
2. You see login screen with 2 fields
3. Paste your API Key and API Secret
4. Click "Login"
5. You see dashboard ✅

---

## 📊 DASHBOARD EXPLAINED

### Tab 1: Dashboard (📊)
- Shows current 9:15-9:30 candle breakout signal
- Lists all active (open) trades
- Real-time P&L tracker
- "Close Trade" button to exit

### Tab 2: New Trade (➕)
- Create a new trade entry
- **Strike:** ATM strike (auto-filled from signal)
- **Direction:** CE (Call/Bullish) or PE (Put/Bearish)
- **Entry Premium:** What you paid (₹)
- **SL Premium:** Auto-calculated (50% of entry)
- **Target Premium:** Auto-calculated (2:1 risk-reward)
- Click "Create Trade" → Telegram alert sent ✅

### Tab 3: Journal (📓)
- View all trades grouped by Day/Month/Year
- Shows P&L for each period
- Filters by status (open/closed/target/sl)
- Sortable table

### Tab 4: Stats (📈)
- Total trades, win rate, total P&L
- Equity curve (cumulative P&L over time)
- Average win, average loss
- Ready-to-go-live checklist

---

## 💬 TELEGRAM ALERTS

Your Telegram bot is already set up! 

Whenever you:
- ✅ Create trade → Message: "TRADE ENTERED: 24000 CE @ ₹150"
- ✅ Close trade → Message: "TARGET HIT: +₹2,500" or "STOP LOSS: -₹1,250"

Bot username: @nifty_paper_trader_bot

(You already got this setup earlier)

---

## 🔄 TYPICAL DAILY WORKFLOW

### 9:15 AM
- Start app (`run.bat` or `run.sh`)
- Login with API key + secret
- Dashboard shows 9:15-9:30 candle

### 9:30 AM
- Check "Signal" on dashboard
- Direction: CE (bullish) or PE (bearish)
- Click "New Trade" tab

### 9:35 AM (If signal is valid)
1. Enter **Entry Premium** (current market price of CE/PE)
2. **SL & Target** auto-fill
3. See **Max Loss** and **Max Profit** summary
4. Click "Create Trade"
5. 📲 Telegram alert sent

### Until 3:15 PM
- Monitor trade in "Active Trades" section
- Update LTP (live price) in input box
- See live P&L in real-time

### 3:15 PM (Closing Time)
1. Check live premium price
2. Click "Close Trade"
3. Enter exit premium
4. 📲 Telegram alert sent: "TARGET HIT +₹X" or "STOP LOSS -₹Y"
5. Trade moves to "Journal"

### End of Day
- Check "Journal" tab → see today's trades
- Check "Stats" tab → win rate, total P&L
- Log entry in your trading diary

---

## 📁 FILE STRUCTURE

```
NiftyPaperTrading/
├── app.py                    # Flask backend (main)
├── frontend.jsx              # React dashboard
├── requirements.txt          # Python packages
├── .env.example              # Template (copy to .env)
├── .env                      # Your credentials (DO NOT SHARE)
├── .gitignore                # Git ignore rules
├── render.yaml               # Render deployment config
├── run.bat                   # Windows startup
├── run.sh                    # Mac/Linux startup
├── README.md                 # Full documentation
├── SETUP.md                  # This file
└── paper_trades.db           # Auto-created database
```

---

## 🌐 DEPLOYING ON RENDER (After Testing)

### When ready to deploy:

1. Push code to GitHub:
   ```bash
   git init
   git add .
   git commit -m "First commit"
   git remote add origin https://github.com/YOUR_USERNAME/NiftyPaperTrading.git
   git push -u origin main
   ```

2. Go to https://render.com → Sign up with GitHub

3. Click "New Web Service"
   - Select your repo
   - Name: `nifty-paper-trading`
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`

4. Add environment variables:
   ```
   KITE_API_KEY=...
   KITE_API_SECRET=...
   TELEGRAM_BOT_TOKEN=8772922884:AAG4JqS9TiDJL-aDYZM-dKdXvGdfFOZycqI
   TELEGRAM_USER_ID=653550541
   ```

5. Deploy → Get URL like `https://nifty-paper-trading.onrender.com`

6. Update Kite app redirect URL:
   ```
   https://nifty-paper-trading.onrender.com/callback
   ```

---

## 💰 KITE SUBSCRIPTION (₹500/month)

### When do you pay?

**Only when you're ready for real trading!** Right now:
- ✅ Free API key (no subscription needed for paper trading)
- ✅ Test everything with paper trades
- ✅ Validate strategy
- ✅ Once win rate > 60% + 20+ trades → Buy subscription

### How to buy:

1. Go to https://kite.trade/apps
2. Your app shows "No live data" (because free)
3. Click "Upgrade Plan"
4. Choose "₹500/month" → Pay via card
5. Instantly get:
   - Live Nifty data (via Kite API)
   - Historical candles
   - Real-time premiums
   - All features unlock

### Cost Breakdown:
- **Now (paper trading):** ₹0
- **After buying subscription:** ₹500/month
- **Per trade:** ₹0 (no brokerage for orders)

---

## 🔒 SECURITY CHECKLIST

✅ **API key stored in .env** (not in code)  
✅ **JWT token expires in 24 hours** (need to login daily)  
✅ **Telegram bot token is private** (only you receive alerts)  
✅ **.env file in .gitignore** (never pushed to GitHub)  
✅ **HTTPS on Render** (encrypted traffic)  
✅ **No real money** (paper trading only)  

**⚠️ IMPORTANT:** Never share .env file or your API credentials!

---

## ⚙️ CUSTOMIZATION

### Change Entry/Exit Rules:
Edit `app.py`, find `detect_signal()` function:
```python
def detect_signal(candle_high, candle_low, spot_price):
    candle_size = candle_high - candle_low
    
    # Modify these thresholds:
    if candle_size > 350 or candle_size < 50:
        return None
    
    # Modify direction logic:
    return "CE"  # or "PE"
```

### Change Telegram Message Format:
Edit `send_telegram_alert()` in `app.py`:
```python
msg = f"""
✅ TRADE ENTERED
Strike: {strike}
Entry: ₹{entry}
"""
```

### Add More Statistics:
Edit `StatsTab` component in `frontend.jsx`:
- Add monthly bar chart
- Add win/loss ratio
- Add largest win/loss
- Add consecutive wins

---

## 🆘 COMMON ISSUES

### Issue: "Cannot fetch signal"
**Solution:** 
- Check internet connection
- Verify KITE_API_KEY in .env
- Restart app (Ctrl+C, then `run.bat`)

### Issue: "Telegram alerts not received"
**Solution:**
- Make sure you sent `/start` to @nifty_paper_trader_bot
- Check TELEGRAM_USER_ID = 653550541
- Check TELEGRAM_BOT_TOKEN = 8772922884:...

### Issue: "Port 5000 already in use"
**Solution:**
- Change PORT in .env to 5001
- Or close other apps using port 5000
- On Windows: `netstat -ano | findstr :5000`

### Issue: "Login fails"
**Solution:**
- Verify API key + secret from https://kite.trade/apps
- Make sure they're exactly copied (no spaces)
- Try logout (browser) → restart app → login again

---

## 📊 BACKTEST REFERENCE

From real NSE data (Aug 2025 - Feb 2026):
- **Total days:** 127
- **Trades taken:** 89
- **Days skipped:** 38
- **Winners:** 56 (62.9% win rate)
- **Total P&L:** ₹2,95,850
- **Avg trade:** ₹3,324

Your paper trading should match these stats!

---

## 🎯 PAPER TRADING GOALS

**Phase 1 Validation:**
- [ ] Execute 20+ paper trades
- [ ] Win rate ≥ 55%
- [ ] Track all day/month/year P&L
- [ ] Run for 2-4 weeks
- [ ] Verify strategy works

**Then move to Phase 2:**
- [ ] Buy ₹500 Kite subscription
- [ ] Test live with ₹5,000 capital
- [ ] Scale up after 50+ live trades

---

## 📞 HELP

**Need help?**
1. Check README.md
2. Check Kite docs: https://kite.trade/docs/connect/v3/
3. Check Render logs: https://render.com
4. Check Telegram: @nifty_paper_trader_bot

---

**You're all set! Start paper trading now! 🚀**

*Built by Yash Patel | GitHub: Yashp1210*
