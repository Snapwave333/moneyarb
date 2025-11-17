<div align="center">

# 📈 MoneyArb - Pairs Trading Bot

<img src="https://img.shields.io/badge/Statistical-Arbitrage-blue?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Statistical Arbitrage"/>

### 🎯 *Find the Edge. Trade the Spread. Profit from Mean Reversion.*

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![NumPy](https://img.shields.io/badge/NumPy-Scientific-013243?style=flat-square&logo=numpy&logoColor=white)](https://numpy.org)
[![Pandas](https://img.shields.io/badge/Pandas-Data-150458?style=flat-square&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![scikit-learn](https://img.shields.io/badge/Statsmodels-Statistics-F7931E?style=flat-square&logo=scipy&logoColor=white)](https://www.statsmodels.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-000000?style=flat-square)](https://black.readthedocs.io)

---

**A sophisticated quantitative trading system that discovers cointegrated stock pairs,**
**monitors their price spreads in real-time, and executes automated mean-reversion trades.**

[🚀 Quick Start](#-quick-start) •
[📖 Documentation](#-how-it-works) •
[⚙️ Configuration](#%EF%B8%8F-configuration) •
[📊 Backtesting](#-backtesting) •
[🛡️ Risk Management](#%EF%B8%8F-risk-management)

</div>

---

## 🌟 What is Pairs Trading?

<table>
<tr>
<td width="50%">

### The Concept
Pairs trading is a **market-neutral** strategy that profits from the relative price movements of two correlated securities—**not** from market direction.

> *"You're not betting on the market. You're betting on the relationship."*

</td>
<td width="50%">

### The Edge
When two historically correlated stocks (like **JPM & BAC** or **Coke & Pepsi**) temporarily diverge, the strategy bets they'll **revert to their mean relationship**.

</td>
</tr>
</table>

```
┌─────────────────────────────────────────────────────────────┐
│                     PAIRS TRADING FLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 SCAN          🔍 MONITOR         ⚡ EXECUTE            │
│  ─────────        ──────────         ─────────             │
│  Find pairs   →   Track spread   →   Trade signal          │
│  that move        & calculate        when spread           │
│  together         z-score            diverges              │
│                                                             │
│  ┌─────┐         ┌─────────┐        ┌──────────┐          │
│  │ JPM │ ≈≈≈≈≈≈  │ Z > +2σ │   →    │ SHORT    │          │
│  │ BAC │         │ Z < -2σ │   →    │ LONG     │          │
│  └─────┘         └─────────┘        └──────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

<table>
<tr>
<td align="center" width="33%">

### 🔬 **Statistical Scanner**
Uses **Engle-Granger cointegration test** to mathematically identify pairs with mean-reverting spreads

</td>
<td align="center" width="33%">

### 📡 **Real-Time Monitor**
Tracks z-scores and generates **automated entry/exit signals** based on statistical thresholds

</td>
<td align="center" width="33%">

### 🤖 **Auto Execution**
Paper trading engine with **position management** and broker API integration ready

</td>
</tr>
<tr>
<td align="center">

### 📈 **Backtesting**
Test strategies on **historical data** with transaction costs, slippage, and performance metrics

</td>
<td align="center">

### 🛡️ **Risk Management**
Built-in **drawdown limits**, position sizing, stop losses, and Kelly criterion

</td>
<td align="center">

### 💾 **Data Pipeline**
**SQLite database** for pairs, trades, and performance with caching system

</td>
</tr>
</table>

---

## 🚀 Quick Start

### 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/moneyarb.git
cd moneyarb

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### ⚡ 5-Minute Demo

```bash
# 1️⃣ Discover cointegrated pairs
python main.py scan --sectors finance

# 2️⃣ Test a specific pair
python main.py test-pair JPM BAC

# 3️⃣ Run historical backtest
python main.py backtest --pairs 10

# 4️⃣ Start paper trading
python main.py paper --duration 1.0

# 5️⃣ Check your status
python main.py status
```

---

## 🎯 CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `scan` | 🔍 Discover cointegrated pairs | `python main.py scan --sectors technology` |
| `test-pair` | 🧪 Test specific pair | `python main.py test-pair AAPL MSFT` |
| `backtest` | 📊 Historical simulation | `python main.py backtest --start 2022-01-01` |
| `paper` | 📝 Paper trading mode | `python main.py paper --duration 8.0` |
| `run` | 🚀 Live trading bot | `python main.py run` |
| `status` | 📈 Current portfolio status | `python main.py status` |
| `history` | 📜 Trade history | `python main.py history --limit 50` |
| `revalidate` | 🔄 Re-check pair validity | `python main.py revalidate` |

---

## 🏗️ Architecture

```
moneyarb/
│
├── 🧠 pairs_trading/              # Core trading engine
│   │
│   ├── 🔬 scanner/                # Pair discovery
│   │   └── cointegration.py      # Engle-Granger tests
│   │
│   ├── 📡 monitor/                # Real-time tracking
│   │   └── spread_monitor.py     # Z-score calculations
│   │
│   ├── ⚡ executor/               # Trade execution
│   │   ├── trade_executor.py     # Order management
│   │   └── risk_manager.py       # Risk controls
│   │
│   ├── 📊 backtest/               # Historical testing
│   │   └── backtester.py         # Strategy simulation
│   │
│   ├── 💾 data/                   # Data management
│   │   ├── fetcher.py            # Market data API
│   │   └── database.py           # SQLite storage
│   │
│   ├── 🔧 utils/                  # Utilities
│   │   ├── config.py             # Configuration
│   │   └── logger.py             # Logging system
│   │
│   └── 🤖 bot.py                  # Main orchestrator
│
├── ⚙️ config/                     # Configuration files
│   └── settings.yaml             # Strategy parameters
│
├── 🧪 tests/                      # Test suite
├── 📜 scripts/                    # Utility scripts
└── 🚀 main.py                     # CLI entry point
```

---

## 📖 How It Works

### 1️⃣ Cointegration Testing

<table>
<tr>
<td width="60%">

The scanner uses the **Engle-Granger two-step method**:

1. **Correlation Check** - Filter pairs with correlation > 0.7
2. **Cointegration Test** - Verify long-term equilibrium exists
3. **ADF Test** - Confirm spread is stationary
4. **Half-Life Calculation** - Estimate mean reversion speed
5. **Hedge Ratio** - Optimal position sizing ratio

</td>
<td width="40%">

```python
# Statistical Tests
✓ Correlation > 0.70
✓ Coint P-Value < 0.05
✓ ADF P-Value < 0.05
✓ Half-Life: 1-120 days
```

</td>
</tr>
</table>

### 2️⃣ Z-Score Signal Generation

```
                    TRADING SIGNALS
    ═══════════════════════════════════════════

         +4σ  ────────── STOP LOSS ──────────

         +2σ  ════════ SHORT SPREAD ════════  ← ENTRY

         +0.5σ -------- EXIT SHORT --------   ← EXIT

          0   ═══════════ MEAN ═══════════

         -0.5σ -------- EXIT LONG ---------   ← EXIT

         -2σ  ════════ LONG SPREAD ═════════  ← ENTRY

         -4σ  ────────── STOP LOSS ──────────
```

### 3️⃣ Mathematical Foundation

<table>
<tr>
<td>

**Spread Calculation:**
```
Spread = Price₁ - β × Price₂
```

**Z-Score:**
```
Z = (Current Spread - μ) / σ
```

**Half-Life:**
```
τ = -ln(2) / λ
```

</td>
<td>

**Trading Rules:**
- **LONG** when Z < -2.0
- **SHORT** when Z > +2.0
- **EXIT** when |Z| < 0.5
- **STOP LOSS** when |Z| > 4.0

</td>
</tr>
</table>

---

## 📊 Backtesting

### Performance Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| 📈 **Total Return** | Absolute profit/loss | > 0 |
| 📊 **Annualized Return** | Yearly CAGR | > 10% |
| ⚖️ **Sharpe Ratio** | Risk-adjusted return | > 1.0 |
| 📉 **Max Drawdown** | Largest peak-to-trough | < 15% |
| 🎯 **Win Rate** | Profitable trades % | > 55% |
| 💰 **Profit Factor** | Gross profit / loss | > 1.5 |
| ⏱️ **Avg Holding Period** | Days per trade | 5-30 |

### Example Backtest Output

```
══════════════════════════════════════════════════
                 BACKTEST RESULTS
══════════════════════════════════════════════════

Performance Metrics:
  Total Return:        $12,450.00 (12.45%)
  Annual Return:       8.23%
  Sharpe Ratio:        1.45
  Max Drawdown:        7.82%

Trade Statistics:
  Total Trades:        156
  Win Rate:            62.18%
  Profit Factor:       1.89
  Avg Trade Return:    $79.81
  Avg Holding Period:  8.3 days
  Best Trade:          $892.00
  Worst Trade:         -$445.00

══════════════════════════════════════════════════
```

---

## ⚙️ Configuration

Edit `config/settings.yaml`:

```yaml
# 🔬 Scanner Parameters
scanner:
  significance_level: 0.05      # Statistical confidence
  min_correlation: 0.7          # Minimum pair correlation
  max_pvalue: 0.05              # Cointegration threshold
  max_pairs: 50                 # Maximum pairs to track

# 📡 Monitor Settings
monitor:
  entry_threshold: 2.0          # Z-score entry (±2σ)
  exit_threshold: 0.5           # Z-score exit (±0.5σ)
  stop_loss_threshold: 4.0      # Stop loss (±4σ)
  update_interval: 60           # Seconds between updates

# 🛡️ Risk Management
risk:
  max_drawdown_pct: 0.15        # 15% max drawdown
  daily_loss_limit: 0.03        # 3% daily loss limit
  max_pair_loss_pct: 0.02       # 2% per-pair loss limit

# 💰 Execution
executor:
  position_size_pct: 0.05       # 5% of portfolio per trade
  max_positions: 10             # Maximum concurrent positions
  paper_capital: 100000.0       # Starting capital
```

---

## 🛡️ Risk Management

<table>
<tr>
<td width="50%">

### Built-in Safeguards

- ✅ **Maximum Drawdown Limit** (15%)
- ✅ **Daily Loss Circuit Breaker** (3%)
- ✅ **Per-Position Loss Limit** (2%)
- ✅ **Maximum Holding Period** (30 days)
- ✅ **Position Size Limits** (5% per trade)
- ✅ **Stop-Loss on Z-Score** (±4σ)

</td>
<td width="50%">

### Risk Metrics Dashboard

```
═══════════════════════════════
       RISK STATUS
═══════════════════════════════
Current Equity: $104,250.00
Peak Equity:    $105,000.00
Current DD:     0.71%
Daily PnL:      +$450.00
Trading Status: ✅ ACTIVE
═══════════════════════════════
```

</td>
</tr>
</table>

---

## 🔌 API Integration

### Supported Data Sources

| Provider | Status | Features |
|----------|--------|----------|
| 📊 **Yahoo Finance** | ✅ Active | Free historical data |
| 🦙 **Alpaca** | 🔧 Ready | Paper + Live trading |
| 🏦 **Interactive Brokers** | 📋 Planned | Professional execution |

### Environment Setup

```bash
# .env file
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
```

---

## ⚠️ Important Disclaimers

<table>
<tr>
<td>

### 🚨 Risk Warnings

1. **NOT FINANCIAL ADVICE** - This is educational software
2. **NO GUARANTEE** - Past performance ≠ future results
3. **CAPITAL AT RISK** - You can lose money
4. **PAPER TRADE FIRST** - Test extensively before live trading
5. **UNDERSTAND THE MATH** - Know what you're trading

</td>
<td>

### 📚 Prerequisites

- Understanding of statistics
- Knowledge of financial markets
- Risk management principles
- Python programming basics
- Patience and discipline

</td>
</tr>
</table>

> **⚡ Pro Tip:** Cointegration can break down. Always revalidate pairs regularly and never risk more than you can afford to lose.

---

## 🧪 Development

```bash
# Run test suite
pytest tests/ -v

# Code formatting
black pairs_trading/

# Type checking
mypy pairs_trading/

# Quick demo
python scripts/quick_demo.py
```

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. 🍴 **Fork** the repository
2. 🌿 **Create** a feature branch (`git checkout -b feature/amazing`)
3. 💻 **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. 📤 **Push** to branch (`git push origin feature/amazing`)
5. 🎉 **Open** a Pull Request

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- 📚 **Ernest P. Chan** - Quantitative trading methodologies
- 📊 **Statsmodels** - Statistical testing framework
- 💹 **yfinance** - Market data API
- 🐍 **Python Scientific Stack** - NumPy, Pandas, SciPy

---

<div align="center">

### ⭐ Star this repo if you find it useful!

**Built with ❤️ for quantitative traders**

[![Made with Python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg?style=for-the-badge&logo=python)](https://www.python.org/)

</div>
