import React, { useState, useEffect } from 'react';

const NiftyPaperTrader = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [token, setToken] = useState(localStorage.getItem('authToken') || '');
  const [trades, setTrades] = useState([]);
  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);

  const API_BASE = 'http://localhost:5000/api';

  // Initialize on mount
  useEffect(() => {
    if (token) {
      setIsLoggedIn(true);
      fetchTrades();
      fetchStats();
      fetchSignal();
    }
  }, [token]);

  // Login handler
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret })
      });

      if (response.ok) {
        const data = await response.json();
        setToken(data.token);
        localStorage.setItem('authToken', data.token);
        setIsLoggedIn(true);
        alert('✅ Login successful!');
      } else {
        alert('❌ Login failed');
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
    setLoading(false);
  };

  // Fetch current signal
  const fetchSignal = async () => {
    try {
      const response = await fetch(`${API_BASE}/signal`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setSignal(data);
      }
    } catch (error) {
      console.error('Signal fetch error:', error);
    }
  };

  // Fetch all trades
  const fetchTrades = async () => {
    try {
      const response = await fetch(`${API_BASE}/trades`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setTrades(data.trades);
      }
    } catch (error) {
      console.error('Trades fetch error:', error);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Stats fetch error:', error);
    }
  };

  // Create new trade
  const handleCreateTrade = async (formData) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/trade`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        alert('✅ Trade created successfully!');
        fetchTrades();
        fetchStats();
      } else {
        alert('❌ Failed to create trade');
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
    setLoading(false);
  };

  // Close trade
  const handleCloseTrade = async (tradeId, exitPremium) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/trade/${tradeId}/close`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ exit_premium: parseFloat(exitPremium) })
      });

      if (response.ok) {
        alert('✅ Trade closed successfully!');
        fetchTrades();
        fetchStats();
      } else {
        alert('❌ Failed to close trade');
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
    setLoading(false);
  };

  // ==================== LOGIN PAGE ====================

  if (!isLoggedIn) {
    return (
      <div style={styles.container}>
        <div style={styles.loginCard}>
          <h1>🚀 Nifty Paper Trader</h1>
          <p style={{ color: '#666', marginBottom: '30px' }}>
            Automated paper trading journal for Nifty 50 options
          </p>

          <form onSubmit={handleLogin} style={styles.form}>
            <div style={styles.formGroup}>
              <label>Zerodha API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Your Kite API key"
                style={styles.input}
                required
              />
            </div>

            <div style={styles.formGroup}>
              <label>API Secret</label>
              <input
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Your Kite API secret"
                style={styles.input}
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={styles.button}
            >
              {loading ? '⏳ Logging in...' : '✅ Login'}
            </button>
          </form>

          <p style={{ fontSize: '12px', color: '#999', marginTop: '20px' }}>
            🔒 Your API credentials are encrypted and stored securely<br/>
            Get your API key from: https://kite.trade/apps
          </p>
        </div>
      </div>
    );
  }

  // ==================== MAIN APP ====================

  return (
    <div style={styles.appContainer}>
      {/* Header */}
      <div style={styles.header}>
        <h1>📈 Nifty Paper Trading Journal</h1>
        <button
          onClick={() => {
            setToken('');
            localStorage.removeItem('authToken');
            setIsLoggedIn(false);
          }}
          style={styles.logoutBtn}
        >
          Logout
        </button>
      </div>

      {/* Tabs */}
      <div style={styles.tabs}>
        {['dashboard', 'new-trade', 'journal', 'stats'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              ...styles.tab,
              ...(activeTab === tab ? styles.tabActive : {})
            }}
          >
            {tab === 'dashboard' && '📊 Dashboard'}
            {tab === 'new-trade' && '➕ New Trade'}
            {tab === 'journal' && '📓 Journal'}
            {tab === 'stats' && '📈 Stats'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={styles.content}>
        {/* DASHBOARD TAB */}
        {activeTab === 'dashboard' && (
          <div>
            <h2>Live Signal & Active Trades</h2>

            {signal && (
              <div style={styles.signalCard}>
                <h3>🔔 Current Signal</h3>
                <p><strong>Spot:</strong> ₹{signal.spot}</p>
                <p><strong>ATM Strike:</strong> {signal.atm_strike}</p>
                <p><strong>Candle High:</strong> ₹{signal.candle_high}</p>
                <p><strong>Candle Low:</strong> ₹{signal.candle_low}</p>
                <p>
                  <strong>Direction:</strong>{' '}
                  <span style={signal.signal ? { color: signal.signal === 'CE' ? 'green' : 'red' } : {}}>
                    {signal.signal ? `${signal.signal} (Bullish/Bearish)` : 'No signal yet'}
                  </span>
                </p>
              </div>
            )}

            <h3 style={{ marginTop: '30px' }}>Active Trades</h3>
            {trades.filter(t => t.status === 'open').length === 0 ? (
              <p style={{ color: '#999' }}>No active trades</p>
            ) : (
              trades.filter(t => t.status === 'open').map((trade) => (
                <div key={trade.trade_id} style={styles.tradeCard}>
                  <div style={styles.tradeHeader}>
                    <h4>{trade.strike} {trade.direction}</h4>
                    <span style={{
                      backgroundColor: trade.direction === 'CE' ? '#90EE90' : '#FFB6C6',
                      padding: '5px 10px',
                      borderRadius: '5px',
                      fontSize: '12px'
                    }}>
                      {trade.direction === 'CE' ? '📈 CALL' : '📉 PUT'}
                    </span>
                  </div>
                  <p><strong>Entry:</strong> ₹{trade.entry_premium} | <strong>SL:</strong> ₹{trade.sl_premium} | <strong>Target:</strong> ₹{trade.target_premium}</p>
                  <div style={styles.liveP_LBar}>
                    <div style={{ flex: 1 }}>
                      <input
                        type="number"
                        step="0.5"
                        placeholder="Current LTP"
                        style={styles.input}
                        defaultValue={trade.entry_premium}
                        onChange={(e) => {
                          // Real-time P&L calculation would go here
                        }}
                      />
                    </div>
                    <button
                      onClick={() => {
                        const exitPrice = prompt('Enter exit premium:');
                        if (exitPrice) {
                          handleCloseTrade(trade.trade_id, exitPrice);
                        }
                      }}
                      style={styles.closeBtn}
                    >
                      Close Trade
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* NEW TRADE TAB */}
        {activeTab === 'new-trade' && (
          <NewTradeForm
            signal={signal}
            onSubmit={handleCreateTrade}
            loading={loading}
          />
        )}

        {/* JOURNAL TAB */}
        {activeTab === 'journal' && (
          <JournalTab trades={trades} />
        )}

        {/* STATS TAB */}
        {activeTab === 'stats' && (
          <StatsTab stats={stats} />
        )}
      </div>
    </div>
  );
};

// ==================== NEW TRADE FORM COMPONENT ====================

const NewTradeForm = ({ signal, onSubmit, loading }) => {
  const [formData, setFormData] = useState({
    date: new Date().toISOString().split('T')[0],
    strike: signal?.atm_strike || 24000,
    direction: 'CE',
    entry_premium: '',
    sl_premium: '',
    target_premium: '',
    candle_high: signal?.candle_high || '',
    candle_low: signal?.candle_low || '',
    spot_price: signal?.spot || ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    const newData = { ...formData, [name]: name === 'strike' ? parseInt(value) : value };

    // Auto-calculate if entry is provided
    if (name === 'entry_premium' && value) {
      const entry = parseFloat(value);
      const sl = Math.round(entry * 0.5);
      const target = Math.round(entry + (entry - sl) * 2);
      newData.sl_premium = sl;
      newData.target_premium = target;
    }

    setFormData(newData);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
    setFormData({ ...formData, entry_premium: '', sl_premium: '', target_premium: '' });
  };

  const entryNum = parseFloat(formData.entry_premium);
  const slNum = parseFloat(formData.sl_premium);
  const maxLoss = isNaN(entryNum) || isNaN(slNum) ? 0 : (entryNum - slNum) * 50;
  const maxProfit = isNaN(entryNum) ? 0 : (parseFloat(formData.target_premium) - entryNum) * 50;

  return (
    <div>
      <h2>➕ Create New Trade</h2>
      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.formRow}>
          <div style={styles.formGroup}>
            <label>Date</label>
            <input
              type="date"
              name="date"
              value={formData.date}
              onChange={handleChange}
              style={styles.input}
            />
          </div>
          <div style={styles.formGroup}>
            <label>Strike</label>
            <input
              type="number"
              name="strike"
              value={formData.strike}
              onChange={handleChange}
              style={styles.input}
            />
          </div>
          <div style={styles.formGroup}>
            <label>Direction</label>
            <select
              name="direction"
              value={formData.direction}
              onChange={handleChange}
              style={styles.input}
            >
              <option value="CE">📈 Call (CE)</option>
              <option value="PE">📉 Put (PE)</option>
            </select>
          </div>
        </div>

        <div style={styles.formRow}>
          <div style={styles.formGroup}>
            <label>Entry Premium (₹)</label>
            <input
              type="number"
              step="0.5"
              name="entry_premium"
              value={formData.entry_premium}
              onChange={handleChange}
              placeholder="e.g., 150"
              style={styles.input}
              required
            />
          </div>
          <div style={styles.formGroup}>
            <label>Stop Loss (₹)</label>
            <input
              type="number"
              step="0.5"
              name="sl_premium"
              value={formData.sl_premium}
              onChange={handleChange}
              placeholder="Auto-calculated: 50% of entry"
              style={styles.input}
              required
            />
          </div>
          <div style={styles.formGroup}>
            <label>Target (₹)</label>
            <input
              type="number"
              step="0.5"
              name="target_premium"
              value={formData.target_premium}
              onChange={handleChange}
              placeholder="Auto-calculated: 2:1 RR"
              style={styles.input}
              required
            />
          </div>
        </div>

        <div style={styles.formRow}>
          <div style={styles.formGroup}>
            <label>Candle High</label>
            <input
              type="number"
              step="1"
              name="candle_high"
              value={formData.candle_high}
              onChange={handleChange}
              style={styles.input}
            />
          </div>
          <div style={styles.formGroup}>
            <label>Candle Low</label>
            <input
              type="number"
              step="1"
              name="candle_low"
              value={formData.candle_low}
              onChange={handleChange}
              style={styles.input}
            />
          </div>
          <div style={styles.formGroup}>
            <label>Spot Price</label>
            <input
              type="number"
              step="1"
              name="spot_price"
              value={formData.spot_price}
              onChange={handleChange}
              style={styles.input}
            />
          </div>
        </div>

        <div style={styles.summary}>
          <h3>Trade Summary</h3>
          <p>Max Loss: <strong style={{ color: 'red' }}>₹{maxLoss}</strong></p>
          <p>Max Profit: <strong style={{ color: 'green' }}>₹{maxProfit}</strong></p>
          <p>Risk-Reward: <strong>1:{maxLoss > 0 ? (maxProfit / maxLoss).toFixed(2) : '?'}</strong></p>
        </div>

        <button type="submit" disabled={loading} style={styles.button}>
          {loading ? '⏳ Creating...' : '✅ Create Trade'}
        </button>
      </form>
    </div>
  );
};

// ==================== JOURNAL COMPONENT ====================

const JournalTab = ({ trades }) => {
  const [viewMode, setViewMode] = useState('day');

  const groupTrades = (mode) => {
    const grouped = {};
    trades.forEach(trade => {
      let key;
      if (mode === 'day') key = trade.date;
      else if (mode === 'month') key = trade.date.slice(0, 7);
      else key = trade.date.slice(0, 4);

      if (!grouped[key]) {
        grouped[key] = { trades: [], pnl: 0, winners: 0, losers: 0 };
      }
      grouped[key].trades.push(trade);
      if (trade.pnl) {
        grouped[key].pnl += trade.pnl;
        if (trade.pnl > 0) grouped[key].winners++;
        else grouped[key].losers++;
      }
    });
    return grouped;
  };

  const grouped = groupTrades(viewMode);

  return (
    <div>
      <h2>📓 Trading Journal</h2>
      <div style={{ marginBottom: '20px' }}>
        {['day', 'month', 'year'].map(mode => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            style={{
              ...styles.tab,
              ...(viewMode === mode ? styles.tabActive : {}),
              marginRight: '10px'
            }}
          >
            By {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </button>
        ))}
      </div>

      {Object.entries(grouped).map(([period, data]) => (
        <div key={period} style={styles.journalCard}>
          <h3>{period}</h3>
          <p>
            Trades: {data.trades.length} | Winners: {data.winners} | Losers: {data.losers} | P&L: <strong style={{ color: data.pnl >= 0 ? 'green' : 'red' }}>₹{data.pnl}</strong>
          </p>
          <table style={styles.table}>
            <thead>
              <tr>
                <th>Date</th>
                <th>Strike</th>
                <th>Dir</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&L</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.trades.map(trade => (
                <tr key={trade.trade_id}>
                  <td>{trade.date}</td>
                  <td>{trade.strike}</td>
                  <td>{trade.direction}</td>
                  <td>₹{trade.entry_premium}</td>
                  <td>{trade.exit_premium ? `₹${trade.exit_premium}` : '-'}</td>
                  <td style={{ color: trade.pnl && trade.pnl >= 0 ? 'green' : 'red' }}>
                    {trade.pnl ? `₹${trade.pnl}` : '-'}
                  </td>
                  <td>{trade.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
};

// ==================== STATS COMPONENT ====================

const StatsTab = ({ stats }) => {
  if (!stats) return <p>Loading stats...</p>;

  return (
    <div>
      <h2>📈 Trading Statistics</h2>
      <div style={styles.statsGrid}>
        <div style={styles.statCard}>
          <h4>Total Trades</h4>
          <p style={styles.bigNumber}>{stats.total_trades}</p>
        </div>
        <div style={styles.statCard}>
          <h4>Closed Trades</h4>
          <p style={styles.bigNumber}>{stats.closed_trades}</p>
        </div>
        <div style={styles.statCard}>
          <h4>Win Rate</h4>
          <p style={{ ...styles.bigNumber, color: stats.win_rate >= 50 ? 'green' : 'red' }}>
            {stats.win_rate}%
          </p>
        </div>
        <div style={styles.statCard}>
          <h4>Total P&L</h4>
          <p style={{ ...styles.bigNumber, color: stats.total_pnl >= 0 ? 'green' : 'red' }}>
            ₹{stats.total_pnl}
          </p>
        </div>
        <div style={styles.statCard}>
          <h4>Winners</h4>
          <p style={{ ...styles.bigNumber, color: 'green' }}>{stats.winners}</p>
        </div>
        <div style={styles.statCard}>
          <h4>Losers</h4>
          <p style={{ ...styles.bigNumber, color: 'red' }}>{stats.losers}</p>
        </div>
        <div style={styles.statCard}>
          <h4>Avg Win</h4>
          <p style={{ ...styles.bigNumber, color: 'green' }}>₹{stats.avg_win}</p>
        </div>
        <div style={styles.statCard}>
          <h4>Avg Loss</h4>
          <p style={{ ...styles.bigNumber, color: 'red' }}>₹{stats.avg_loss}</p>
        </div>
      </div>

      <h3 style={{ marginTop: '40px' }}>Equity Curve</h3>
      <div style={styles.chartPlaceholder}>
        📊 Equity chart will be displayed here (integrate with recharts library)
        <br/>
        <small>Total Equity: ₹{stats.total_pnl}</small>
      </div>
    </div>
  );
};

// ==================== STYLES ====================

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    padding: '20px',
    fontFamily: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'
  },
  loginCard: {
    backgroundColor: 'white',
    padding: '40px',
    borderRadius: '10px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
    width: '100%',
    maxWidth: '400px'
  },
  appContainer: {
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    fontFamily: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'
  },
  header: {
    backgroundColor: '#1e88e5',
    color: 'white',
    padding: '20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  logoutBtn: {
    backgroundColor: '#dc3545',
    color: 'white',
    border: 'none',
    padding: '8px 16px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px'
  },
  tabs: {
    display: 'flex',
    backgroundColor: 'white',
    borderBottom: '2px solid #ddd',
    padding: '0 20px'
  },
  tab: {
    backgroundColor: 'transparent',
    border: 'none',
    padding: '15px 20px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    color: '#666',
    borderBottom: '3px solid transparent'
  },
  tabActive: {
    color: '#1e88e5',
    borderBottomColor: '#1e88e5'
  },
  content: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '30px 20px',
    backgroundColor: 'white',
    minHeight: 'calc(100vh - 120px)'
  },
  form: {
    display: 'flex',
    flexDirection: 'column'
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    marginBottom: '15px'
  },
  formRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '15px',
    marginBottom: '15px'
  },
  input: {
    padding: '10px',
    border: '1px solid #ddd',
    borderRadius: '5px',
    fontSize: '14px',
    fontFamily: 'Segoe UI'
  },
  button: {
    backgroundColor: '#1e88e5',
    color: 'white',
    padding: '12px',
    border: 'none',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '600',
    marginTop: '20px'
  },
  closeBtn: {
    backgroundColor: '#dc3545',
    color: 'white',
    padding: '10px 20px',
    border: 'none',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '12px'
  },
  signalCard: {
    backgroundColor: '#e3f2fd',
    padding: '20px',
    borderRadius: '10px',
    marginBottom: '20px',
    border: '2px solid #1e88e5'
  },
  tradeCard: {
    backgroundColor: '#f9f9f9',
    padding: '15px',
    borderRadius: '8px',
    marginBottom: '15px',
    border: '1px solid #ddd'
  },
  tradeHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '10px'
  },
  liveP_LBar: {
    display: 'flex',
    gap: '10px',
    marginTop: '10px'
  },
  summary: {
    backgroundColor: '#fff3cd',
    padding: '15px',
    borderRadius: '5px',
    marginTop: '20px',
    marginBottom: '20px'
  },
  journalCard: {
    backgroundColor: '#f9f9f9',
    padding: '20px',
    borderRadius: '8px',
    marginBottom: '20px',
    border: '1px solid #ddd'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    marginTop: '10px'
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: '15px',
    marginTop: '20px'
  },
  statCard: {
    backgroundColor: '#f0f0f0',
    padding: '20px',
    borderRadius: '8px',
    textAlign: 'center',
    border: '1px solid #ddd'
  },
  bigNumber: {
    fontSize: '32px',
    fontWeight: 'bold',
    margin: '10px 0',
    color: '#1e88e5'
  },
  chartPlaceholder: {
    backgroundColor: '#f0f0f0',
    padding: '60px',
    borderRadius: '8px',
    textAlign: 'center',
    color: '#999',
    marginTop: '20px'
  }
};

export default NiftyPaperTrader;
