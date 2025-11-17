#!/usr/bin/env python3
"""
Quick demonstration of the pairs trading bot.

This script shows a complete workflow:
1. Scan for pairs
2. Test a specific pair
3. Run a backtest
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pairs_trading.scanner.cointegration import CointegrationScanner
from pairs_trading.backtest.backtester import PairsBacktester
from pairs_trading.data.fetcher import DataFetcher
from pairs_trading.utils.logger import setup_logger

logger = setup_logger("demo")


def main():
    print("=" * 60)
    print("PAIRS TRADING BOT - QUICK DEMO")
    print("=" * 60)

    # 1. Test a known correlated pair
    print("\n1. Testing a known correlated pair (JPM-BAC)...")
    fetcher = DataFetcher()
    scanner = CointegrationScanner()

    # Fetch data
    prices = fetcher.fetch_historical_data(["JPM", "BAC"])

    # Test cointegration
    result = scanner.test_pair("JPM", "BAC", prices["JPM"], prices["BAC"])

    print(f"   Cointegration P-Value: {result.coint_pvalue:.4f}")
    print(f"   Correlation: {result.correlation:.4f}")
    print(f"   Hedge Ratio: {result.hedge_ratio:.4f}")
    print(f"   Half-Life: {result.half_life:.1f} days")
    print(f"   Valid for trading: {result.is_valid}")

    # 2. Scan a small universe
    print("\n2. Scanning financial sector for pairs...")
    symbols = fetcher.get_sector_symbols("finance")[:10]
    print(f"   Scanning {len(symbols)} symbols...")

    pairs = scanner.scan_universe(symbols)
    print(f"   Found {len(pairs)} cointegrated pairs")

    if pairs:
        print("\n   Top 3 pairs:")
        for i, pair in enumerate(pairs[:3], 1):
            print(f"   {i}. {pair.symbol1}-{pair.symbol2} (p-value: {pair.coint_pvalue:.4f})")

    # 3. Run a quick backtest
    if pairs:
        print("\n3. Running backtest on discovered pairs...")
        backtester = PairsBacktester()
        result = backtester.run_backtest(pairs[:5], start_date="-1y")

        print(f"   Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)")
        print(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"   Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"   Win Rate: {result.win_rate:.2f}%")
        print(f"   Total Trades: {result.total_trades}")

    print("\n" + "=" * 60)
    print("Demo complete! Run 'python main.py --help' for full CLI")
    print("=" * 60)


if __name__ == "__main__":
    main()
