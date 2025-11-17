# Statistical Arbitrage (Pairs Trading) Bot

A comprehensive Python-based system for discovering cointegrated stock pairs, monitoring their price spreads, and executing mean-reversion trades automatically.

## Overview

This bot implements a classic quantitative trading strategy known as **pairs trading** or **statistical arbitrage**. The core concept:

1. **Find correlated pairs**: Identify two stocks that historically move together (e.g., Coke & Pepsi, JPM & BAC)
2. **Monitor the spread**: Track when their price relationship temporarily breaks down
3. **Trade the reversion**: When the spread widens beyond normal, bet it will revert to the mean

## Features

- **Cointegration Scanner**: Uses Engle-Granger test to find mathematically cointegrated pairs
- **Real-time Monitoring**: Tracks z-scores and generates entry/exit signals
- **Automated Execution**: Paper trading with broker API integration ready
- **Backtesting Framework**: Test strategies on historical data with realistic costs
- **Risk Management**: Drawdown limits, position sizing, and stop losses
- **Database Storage**: SQLite for pairs, trades, and performance metrics
- **CLI Interface**: Easy-to-use command-line tools

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd moneyarb

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### 1. Scan for Cointegrated Pairs

```bash
# Scan default universe (60 liquid stocks)
python main.py scan

# Scan specific sectors
python main.py scan --sectors technology --sectors finance

# Scan specific symbols
python main.py scan -s AAPL -s MSFT -s GOOGL -s META
```

### 2. Test a Specific Pair

```bash
# Test if two stocks are cointegrated
python main.py test-pair AAPL MSFT
```

### 3. Backtest Strategy

```bash
# Run backtest on top pairs over last 2 years
python main.py backtest

# Custom date range
python main.py backtest --start 2022-01-01 --end 2024-01-01

# Test more pairs
python main.py backtest --pairs 20
```

### 4. Paper Trading

```bash
# Run paper trading for 1 hour
python main.py paper --duration 1.0

# Run for 8 hours (full trading day)
python main.py paper --duration 8.0
```

### 5. Check Status

```bash
# View current status
python main.py status

# View trade history
python main.py history --limit 50
```

## Architecture

```
pairs_trading/
├── scanner/           # Cointegration pair discovery
│   └── cointegration.py
├── monitor/           # Real-time spread monitoring
│   └── spread_monitor.py
├── executor/          # Trade execution engine
│   ├── trade_executor.py
│   └── risk_manager.py
├── backtest/          # Historical backtesting
│   └── backtester.py
├── data/              # Data management
│   ├── fetcher.py     # Market data fetching
│   └── database.py    # SQLite storage
├── utils/             # Utilities
│   ├── config.py      # Configuration management
│   └── logger.py      # Logging setup
└── bot.py             # Main orchestrator
```

## Configuration

Edit `config/settings.yaml` to customize:

```yaml
# Scanner settings
scanner:
  significance_level: 0.05
  min_correlation: 0.7
  max_pvalue: 0.05
  max_pairs: 50

# Monitor settings
monitor:
  entry_threshold: 2.0      # Z-score to enter trade
  exit_threshold: 0.5       # Z-score to exit trade
  stop_loss_threshold: 4.0  # Stop loss z-score

# Risk management
risk:
  max_drawdown_pct: 0.15
  daily_loss_limit: 0.03
  max_pair_loss_pct: 0.02
```

## How It Works

### 1. Cointegration Testing

The scanner uses the **Engle-Granger two-step method**:
- Tests if two price series are cointegrated (move together long-term)
- Calculates the optimal **hedge ratio** (β) for the spread
- Verifies the spread is **stationary** using the ADF test
- Estimates **half-life** of mean reversion

### 2. Z-Score Calculation

```
Spread = Price₁ - β × Price₂
Z-Score = (Current Spread - Mean) / Std
```

### 3. Trading Logic

- **Entry Signal**: Z-score crosses ±2.0 standard deviations
  - Negative z-score → Long spread (buy stock1, sell stock2)
  - Positive z-score → Short spread (sell stock1, buy stock2)
- **Exit Signal**: Z-score returns to ±0.5 (mean reversion)
- **Stop Loss**: Z-score exceeds ±4.0

### 4. Example Trade

```
Pair: AAPL-MSFT
Hedge Ratio: 0.85
Mean Spread: $15.00
Std Spread: $2.50

Current: AAPL=$150, MSFT=$158
Current Spread = $150 - 0.85×$158 = $15.70
Z-Score = ($15.70 - $15.00) / $2.50 = 0.28

No signal (z-score within normal range)

Later: AAPL=$155, MSFT=$160
Current Spread = $155 - 0.85×$160 = $19.00
Z-Score = ($19.00 - $15.00) / $2.50 = 1.60

Still no signal...

Later: AAPL=$160, MSFT=$161
Current Spread = $160 - 0.85×$161 = $23.15
Z-Score = ($23.15 - $15.00) / $2.50 = 3.26

Signal: SHORT SPREAD (sell AAPL, buy MSFT)
Expecting spread to decrease back toward $15.00
```

## Performance Metrics

The backtester calculates:
- **Total Return**: Absolute and percentage
- **Annualized Return**: Compounded annual growth rate
- **Sharpe Ratio**: Risk-adjusted return (>1.0 is good)
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / Gross loss
- **Average Holding Period**: Days per trade

## API Integration

For live trading, configure broker credentials in `.env`:

```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
```

Supported brokers (implementations ready for extension):
- Paper Trading (default)
- Alpaca (planned)
- Interactive Brokers (planned)

## Risk Warnings

**IMPORTANT**: This is a sophisticated trading system with significant risks:

1. **Statistical arbitrage is not risk-free** - Cointegration can break down
2. **Past performance doesn't guarantee future results**
3. **Paper trade extensively** before considering real money
4. **Understand the mathematics** before deploying
5. **Market conditions change** - Regular revalidation is essential

## Development

```bash
# Run tests
pytest tests/

# Format code
black pairs_trading/

# Type checking
mypy pairs_trading/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- Engle-Granger cointegration test (statsmodels)
- Yahoo Finance API (yfinance)
- Inspired by Ernest Chan's quantitative trading books
