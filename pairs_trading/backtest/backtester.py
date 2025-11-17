"""
Backtesting framework for pairs trading strategies.

Simulates historical trading to evaluate strategy performance.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..data.fetcher import DataFetcher
from ..scanner.cointegration import CointegrationScanner, PairResult

logger = setup_logger(__name__)


@dataclass
class BacktestTrade:
    """A single trade in the backtest."""
    entry_date: datetime
    exit_date: datetime
    symbol1: str
    symbol2: str
    entry_price1: float
    entry_price2: float
    exit_price1: float
    exit_price2: float
    quantity1: float
    quantity2: float
    entry_zscore: float
    exit_zscore: float
    pnl: float
    return_pct: float
    holding_days: int


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    total_return: float
    total_return_pct: float
    annual_return_pct: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_return: float
    avg_holding_period: float
    best_trade: float
    worst_trade: float
    equity_curve: pd.Series
    trades: List[BacktestTrade]


class PairsBacktester:
    """
    Backtesting engine for pairs trading strategies.

    Features:
    - Historical simulation with realistic execution
    - Transaction costs and slippage modeling
    - Performance metrics calculation
    - Equity curve generation
    """

    def __init__(self):
        self.config = get_config()
        self.fetcher = DataFetcher()
        self.scanner = CointegrationScanner()

        # Backtest parameters
        self.initial_capital = self.config.get("backtest.initial_capital", 100000.0)
        self.transaction_cost = self.config.get("backtest.transaction_cost", 0.001)
        self.slippage = self.config.get("backtest.slippage", 0.0005)

        # Trading parameters
        self.entry_threshold = self.config.get("monitor.entry_threshold", 2.0)
        self.exit_threshold = self.config.get("monitor.exit_threshold", 0.5)
        self.stop_loss_threshold = self.config.get("monitor.stop_loss_threshold", 4.0)
        self.position_size_pct = self.config.get("executor.position_size_pct", 0.05)
        self.max_positions = self.config.get("executor.max_positions", 10)

        # Risk parameters
        self.max_holding_period = self.config.get("risk.max_holding_period", 30)

    def run_backtest(
        self,
        pairs: List[PairResult],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> BacktestResult:
        """
        Run a full backtest on given pairs.

        Args:
            pairs: List of cointegrated pairs to trade
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            BacktestResult with performance metrics
        """
        # Parse dates
        if start_date is None:
            start_date = self._parse_date(self.config.get("backtest.start_date", "-2y"))
        if end_date is None:
            end_date = self._parse_date(self.config.get("backtest.end_date", "today"))

        logger.info(f"Running backtest from {start_date} to {end_date}")
        logger.info(f"Testing {len(pairs)} pairs")

        # Get all unique symbols
        symbols = set()
        for pair in pairs:
            symbols.add(pair.symbol1)
            symbols.add(pair.symbol2)

        # Fetch historical data
        prices = self.fetcher.fetch_historical_data(
            list(symbols),
            start_date=start_date,
            end_date=end_date,
            use_cache=True
        )

        # Filter prices to date range
        prices = prices.loc[start_date:end_date]

        # Initialize backtest state
        cash = self.initial_capital
        equity_history = []
        trades = []
        active_positions = {}  # pair_key -> position info

        # Iterate through each day
        for date_idx in range(len(prices)):
            current_date = prices.index[date_idx]
            daily_prices = prices.iloc[date_idx]

            # Check exit conditions for active positions
            positions_to_close = []
            for pair_key, pos in active_positions.items():
                symbol1, symbol2 = pair_key.split("_")

                if symbol1 not in daily_prices or symbol2 not in daily_prices:
                    continue

                current_spread = daily_prices[symbol1] - pos['hedge_ratio'] * daily_prices[symbol2]
                zscore = (current_spread - pos['mean_spread']) / pos['std_spread']

                # Check exit conditions
                should_exit = False
                exit_reason = ""

                # Mean reversion exit
                if pos['position_type'] == 'long' and zscore > -self.exit_threshold:
                    should_exit = True
                    exit_reason = "mean_reversion"
                elif pos['position_type'] == 'short' and zscore < self.exit_threshold:
                    should_exit = True
                    exit_reason = "mean_reversion"

                # Stop loss
                if abs(zscore) > self.stop_loss_threshold:
                    should_exit = True
                    exit_reason = "stop_loss"

                # Max holding period
                holding_days = (current_date - pos['entry_date']).days
                if holding_days >= self.max_holding_period:
                    should_exit = True
                    exit_reason = "max_holding"

                if should_exit:
                    positions_to_close.append((pair_key, zscore, exit_reason))

            # Close positions
            for pair_key, exit_zscore, reason in positions_to_close:
                pos = active_positions[pair_key]
                symbol1, symbol2 = pair_key.split("_")

                exit_price1 = daily_prices[symbol1] * (1 - self.slippage)
                exit_price2 = daily_prices[symbol2] * (1 + self.slippage)

                # Calculate PnL
                pnl1 = pos['quantity1'] * (exit_price1 - pos['entry_price1'])
                pnl2 = pos['quantity2'] * (exit_price2 - pos['entry_price2'])
                gross_pnl = pnl1 + pnl2

                # Transaction costs
                exit_value = abs(pos['quantity1'] * exit_price1) + abs(pos['quantity2'] * exit_price2)
                costs = exit_value * self.transaction_cost
                net_pnl = gross_pnl - costs

                # Update cash
                cash += pos['entry_value'] + net_pnl

                # Record trade
                trade = BacktestTrade(
                    entry_date=pos['entry_date'],
                    exit_date=current_date,
                    symbol1=symbol1,
                    symbol2=symbol2,
                    entry_price1=pos['entry_price1'],
                    entry_price2=pos['entry_price2'],
                    exit_price1=exit_price1,
                    exit_price2=exit_price2,
                    quantity1=pos['quantity1'],
                    quantity2=pos['quantity2'],
                    entry_zscore=pos['entry_zscore'],
                    exit_zscore=exit_zscore,
                    pnl=net_pnl,
                    return_pct=net_pnl / pos['entry_value'] * 100,
                    holding_days=(current_date - pos['entry_date']).days
                )
                trades.append(trade)

                del active_positions[pair_key]
                logger.debug(f"Closed {pair_key} ({reason}): PnL=${net_pnl:.2f}")

            # Check entry conditions for all pairs
            if len(active_positions) < self.max_positions:
                for pair in pairs:
                    pair_key = f"{pair.symbol1}_{pair.symbol2}"

                    if pair_key in active_positions:
                        continue

                    if pair.symbol1 not in daily_prices or pair.symbol2 not in daily_prices:
                        continue

                    # Calculate current z-score
                    current_spread = (
                        daily_prices[pair.symbol1] - pair.hedge_ratio * daily_prices[pair.symbol2]
                    )
                    zscore = (current_spread - pair.mean_spread) / pair.std_spread

                    # Check entry signals
                    if zscore < -self.entry_threshold:
                        # Long spread: buy stock1, sell stock2
                        if self._enter_position(
                            cash, daily_prices, pair, zscore, 'long', active_positions, pair_key, current_date
                        ):
                            cash -= active_positions[pair_key]['entry_value']

                    elif zscore > self.entry_threshold:
                        # Short spread: sell stock1, buy stock2
                        if self._enter_position(
                            cash, daily_prices, pair, zscore, 'short', active_positions, pair_key, current_date
                        ):
                            cash -= active_positions[pair_key]['entry_value']

                    if len(active_positions) >= self.max_positions:
                        break

            # Calculate current equity
            positions_value = 0.0
            for pair_key, pos in active_positions.items():
                symbol1, symbol2 = pair_key.split("_")
                if symbol1 in daily_prices and symbol2 in daily_prices:
                    positions_value += pos['quantity1'] * daily_prices[symbol1]
                    positions_value += pos['quantity2'] * daily_prices[symbol2]

            total_equity = cash + positions_value
            equity_history.append(total_equity)

        # Create equity curve
        equity_curve = pd.Series(equity_history, index=prices.index)

        # Calculate performance metrics
        result = self._calculate_metrics(equity_curve, trades)

        return result

    def _enter_position(
        self,
        cash: float,
        prices: pd.Series,
        pair: PairResult,
        zscore: float,
        position_type: str,
        active_positions: Dict,
        pair_key: str,
        current_date: datetime
    ) -> bool:
        """Enter a new position if capital is available."""
        # Calculate position size
        capital_for_trade = (cash + sum(p['entry_value'] for p in active_positions.values())) * self.position_size_pct

        if capital_for_trade > cash:
            return False

        price1 = prices[pair.symbol1]
        price2 = prices[pair.symbol2]

        # Apply slippage
        if position_type == 'long':
            # Buy stock1, sell stock2
            entry_price1 = price1 * (1 + self.slippage)
            entry_price2 = price2 * (1 - self.slippage)
            qty1 = capital_for_trade / (entry_price1 + pair.hedge_ratio * entry_price2)
            qty2 = -qty1 * pair.hedge_ratio
        else:
            # Sell stock1, buy stock2
            entry_price1 = price1 * (1 - self.slippage)
            entry_price2 = price2 * (1 + self.slippage)
            qty1 = -capital_for_trade / (entry_price1 + pair.hedge_ratio * entry_price2)
            qty2 = -qty1 * pair.hedge_ratio

        # Calculate entry value (capital used)
        entry_value = abs(qty1 * entry_price1) + abs(qty2 * entry_price2)

        # Transaction costs
        entry_value += entry_value * self.transaction_cost

        if entry_value > cash:
            return False

        # Store position
        active_positions[pair_key] = {
            'symbol1': pair.symbol1,
            'symbol2': pair.symbol2,
            'quantity1': qty1,
            'quantity2': qty2,
            'entry_price1': entry_price1,
            'entry_price2': entry_price2,
            'hedge_ratio': pair.hedge_ratio,
            'mean_spread': pair.mean_spread,
            'std_spread': pair.std_spread,
            'entry_zscore': zscore,
            'entry_date': current_date,
            'entry_value': entry_value,
            'position_type': position_type
        }

        logger.debug(f"Entered {position_type} {pair_key}: z-score={zscore:.2f}")
        return True

    def _calculate_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[BacktestTrade]
    ) -> BacktestResult:
        """Calculate comprehensive performance metrics."""
        # Basic returns
        total_return = equity_curve.iloc[-1] - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100

        # Annualized return
        num_days = len(equity_curve)
        years = num_days / 252
        annual_return_pct = ((equity_curve.iloc[-1] / self.initial_capital) ** (1 / years) - 1) * 100

        # Daily returns for Sharpe ratio
        daily_returns = equity_curve.pct_change().dropna()
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std()
        else:
            sharpe_ratio = 0.0

        # Maximum drawdown
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min()) * 100

        # Trade statistics
        if trades:
            pnls = [t.pnl for t in trades]
            winning_trades = [p for p in pnls if p > 0]
            losing_trades = [p for p in pnls if p <= 0]

            win_rate = len(winning_trades) / len(trades) * 100
            avg_trade_return = np.mean(pnls)
            avg_holding_period = np.mean([t.holding_days for t in trades])

            if losing_trades and sum(losing_trades) != 0:
                profit_factor = sum(winning_trades) / abs(sum(losing_trades))
            else:
                profit_factor = float('inf') if winning_trades else 0.0

            best_trade = max(pnls) if pnls else 0.0
            worst_trade = min(pnls) if pnls else 0.0
        else:
            win_rate = 0.0
            avg_trade_return = 0.0
            avg_holding_period = 0.0
            profit_factor = 0.0
            best_trade = 0.0
            worst_trade = 0.0

        return BacktestResult(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annual_return_pct=annual_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trades),
            avg_trade_return=avg_trade_return,
            avg_holding_period=avg_holding_period,
            best_trade=best_trade,
            worst_trade=worst_trade,
            equity_curve=equity_curve,
            trades=trades
        )

    def _parse_date(self, date_str: str) -> str:
        """Parse date string, supporting relative dates."""
        if date_str == "today":
            return datetime.now().strftime("%Y-%m-%d")
        elif date_str.startswith("-"):
            # Relative date like -2y, -6m, -30d
            num = int(date_str[1:-1])
            unit = date_str[-1]

            if unit == 'y':
                delta = timedelta(days=num * 365)
            elif unit == 'm':
                delta = timedelta(days=num * 30)
            elif unit == 'd':
                delta = timedelta(days=num)
            else:
                raise ValueError(f"Unknown date unit: {unit}")

            return (datetime.now() - delta).strftime("%Y-%m-%d")
        else:
            return date_str

    def print_results(self, result: BacktestResult) -> None:
        """Print backtest results in a formatted way."""
        print("\n" + "=" * 50)
        print("BACKTEST RESULTS")
        print("=" * 50)

        print(f"\nPerformance Metrics:")
        print(f"  Total Return:        ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)")
        print(f"  Annual Return:       {result.annual_return_pct:.2f}%")
        print(f"  Sharpe Ratio:        {result.sharpe_ratio:.2f}")
        print(f"  Max Drawdown:        {result.max_drawdown:.2f}%")

        print(f"\nTrade Statistics:")
        print(f"  Total Trades:        {result.total_trades}")
        print(f"  Win Rate:            {result.win_rate:.2f}%")
        print(f"  Profit Factor:       {result.profit_factor:.2f}")
        print(f"  Avg Trade Return:    ${result.avg_trade_return:.2f}")
        print(f"  Avg Holding Period:  {result.avg_holding_period:.1f} days")
        print(f"  Best Trade:          ${result.best_trade:.2f}")
        print(f"  Worst Trade:         ${result.worst_trade:.2f}")

        print("\n" + "=" * 50)
