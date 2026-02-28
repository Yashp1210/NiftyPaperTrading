# Nifty Paper Trading System

A secure, automated paper trading journal for managing options trades with real-time alerts and comprehensive analytics.

---

## 📋 What's Included

✅ **Flask Backend** - Secure API with JWT authentication  
✅ **Web Dashboard** - Real-time trade management interface  
✅ **SQLite Database** - Persistent trade history and analytics  
✅ **Telegram Bot** - Real-time trade alerts and notifications  
✅ **JWT Security** - Protected API endpoints  
✅ **Production Ready** - Deploy on Render in minutes  

---

## 🔧 QUICK START (Local Development)

### 1. Clone & Setup

```bash
# Extract the repository
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
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
```

### 3. Run Locally

```bash
# Start backend server (http://localhost:5000)
python app.py
```

The app will:
- ✅ Create SQLite database automatically
- ✅ Start Flask server on localhost:5000
- ✅ Initialize API connections
- ✅ Listen for API requests

---

## 🔑 Required Credentials

### A. Telegram Bot Token

Create a bot via **@BotFather** on Telegram:
1. Search for **@BotFather**
2. Send `/newbot`
3. Follow the setup instructions
4. Copy your bot token

Add to `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_user_id_here
```

### B. Zerodha Kite API Key

Visit: https://kite.trade/apps

1. Click "Create New App"
2. Configure:
   - **App Name:** `NiftyPaperTrading`
   - **App Type:** `Trade`
   - **Redirect URL:** `http://localhost:5000/callback` (local) OR `https://nifty-paper-trading.onrender.com/callback` (production)

3. Note your credentials:
   - `API_KEY`
   - `API_SECRET`

4. Add to `.env`

### C. Kite Access Token

1. Complete OAuth flow via Kite
2. Obtain your access token
3. Add to `.env`

---

## 📝 Environment Configuration

Create `.env` in the root directory:

```env
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
PORT=5000

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_user_id_here

# Zerodha Kite API
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here

# Database
DATABASE_URL=sqlite:///paper_trades.db

# JWT Settings
JWT_EXPIRY_HOURS=24
```

**⚠️ SECURITY:** Never push `.env` to version control!

---

## 🌐 Deploy on Render (FREE)

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/NiftyPaperTrading.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to https://render.com
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your `NiftyPaperTrading` repository
5. Configure:
   - **Name:** `nifty-paper-trading`
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`

### Step 3: Add Environment Variables

In Render dashboard:

1. Go to "Settings" → "Environment"
2. Add all variables from your `.env` file
3. Click "Save"

Your app will be live at:
```
https://nifty-paper-trading.onrender.com
```

### Step 4: Update Kite Redirect URL

Update your app at https://kite.trade/apps:

```
Redirect URL: https://nifty-paper-trading.onrender.com/callback
```

---

## 📡 API Endpoints

All endpoints require JWT authentication:

```
Authorization: Bearer <your_token>
```

### Authentication
```
POST /api/login
```

### Trade Management
```
POST /api/trade
GET /api/trades
PUT /api/trade/<id>/close
```

### Analytics
```
GET /api/journal
GET /api/stats
```

### System
```
GET /api/health
```

For full API documentation, see `app.py` or contact the administrator.

---

## 🔒 Security

✅ JWT token-based authentication  
✅ Secure credential storage  
✅ CORS protection  
✅ HTTPS/SSL encryption (Render)  
✅ Database encryption support  
✅ No credentials in version control  

---

## 📊 Features

- Real-time trade entry and exit
- Comprehensive trade history
- Performance analytics and statistics
- Telegram notification system
- Secure API endpoints
- Scalable SQLite database
- Cloud deployment ready

---

## 🚀 Usage Workflow

1. **Login** - Authenticate with your credentials
2. **Create Trades** - Log entry and exit details
3. **Get Alerts** - Receive notifications via Telegram
4. **Track Performance** - Monitor statistics and history
5. **Analyze Results** - Review comprehensive analytics

---

## 🐛 Troubleshooting

### Connection Issues
- Verify all credentials in `.env`
- Check internet connectivity
- Ensure Kite subscription is active

### Telegram Alerts Not Working
- Verify bot token and user ID
- Ensure Telegram connection is active
- Check bot privacy settings

### Port Conflicts
- Change `PORT` in `.env`
- Or kill existing process on the port

---

## 📞 Support

- **Kite API Documentation:** https://kite.trade/docs/connect/v3/
- **Render Documentation:** https://render.com/docs
- **Telegram Bot API:** https://core.telegram.org/bots/api

---

## 📝 License

For personal use only. Redistribution prohibited without permission.

---

## 🎯 Project Status

- ✅ Core functionality complete
- ✅ API endpoints working
- ✅ Database persistence verified
- ✅ Telegram integration operational
- ✅ Cloud deployment ready

---

**Developed by Yash Patel**  
**GitHub:** Yashp1210  
**Created:** Feb 28, 2026