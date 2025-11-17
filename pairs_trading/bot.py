"""
Main orchestrator for the pairs trading bot.

Coordinates scanning, monitoring, and execution in a unified workflow.
"""

import time
from datetime import datetime, timedelta
from typing import Optional, List
import signal
import sys

from .utils.config import get_config
from .utils.logger import setup_logger
from .scanner.cointegration import CointegrationScanner
from .monitor.spread_monitor import SpreadMonitor, SignalType
from .executor.trade_executor import TradeExecutor
from .executor.risk_manager import RiskManager
from .data.fetcher import DataFetcher
from .data.database import Database

logger = setup_logger("pairs_trading_bot")


class PairsTradingBot:
    """
    Main pairs trading bot orchestrator.

    Coordinates:
    1. Pair discovery (scanning for cointegrated pairs)
    2. Spread monitoring (tracking z-scores in real-time)
    3. Signal generation (entry/exit signals)
    4. Trade execution (placing orders)
    5. Risk management (monitoring portfolio risk)
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the bot with optional config path."""
        self.config = get_config()
        if config_path:
            self.config.load_from_file(config_path)

        # Initialize components
        self.scanner = CointegrationScanner()
        self.monitor = SpreadMonitor()
        self.executor = TradeExecutor()
        self.risk_manager = RiskManager()
        self.fetcher = DataFetcher()
        self.db = Database()

        # Bot state
        self.running = False
        self.last_scan_time = None
        self.last_revalidation_time = None

        # Parameters
        self.update_interval = self.config.get("monitor.update_interval", 60)
        self.scan_interval_days = 7  # Rescan for pairs weekly
        self.revalidation_interval_days = 1  # Revalidate daily

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received. Stopping bot...")
        self.running = False

    def scan_pairs(self, symbols: Optional[List[str]] = None) -> int:
        """
        Scan for cointegrated pairs.

        Args:
            symbols: Optional list of symbols to scan

        Returns:
            Number of valid pairs found
        """
        logger.info("Starting pair scanning...")

        if symbols is None:
            universe = self.config.get("scanner.universe", [])
            if not universe:
                sectors = self.config.get("scanner.sectors", [])
                if sectors:
                    symbols = []
                    for sector in sectors:
                        symbols.extend(self.fetcher.get_sector_symbols(sector))
                else:
                    symbols = self.fetcher._get_default_universe()

        # Run the scan
        pairs = self.scanner.scan_universe(symbols)

        # Save to database
        self.scanner.save_pairs_to_db(pairs)

        # Log statistics
        stats = self.scanner.get_pair_statistics(pairs)
        logger.info(f"Scan complete. Found {stats.get('num_pairs', 0)} valid pairs")
        logger.info(f"Average p-value: {stats.get('avg_pvalue', 0):.4f}")
        logger.info(f"Average half-life: {stats.get('avg_half_life', 0):.1f} days")

        self.last_scan_time = datetime.now()
        return len(pairs)

    def initialize(self) -> bool:
        """
        Initialize the bot for trading.

        Returns:
            True if initialization successful
        """
        logger.info("Initializing Pairs Trading Bot...")

        # Check if we have pairs in database
        active_pairs = self.db.get_active_pairs()

        if not active_pairs:
            logger.info("No active pairs found. Running initial scan...")
            num_pairs = self.scan_pairs()
            if num_pairs == 0:
                logger.error("No cointegrated pairs found. Cannot start trading.")
                return False

        # Initialize monitor with database pairs
        self.monitor.initialize_pairs()

        # Load any open positions
        open_trades = self.db.get_open_trades()
        logger.info(f"Found {len(open_trades)} open positions")

        # Update risk manager with current equity
        account_info = self.executor.broker.get_account_info()
        self.risk_manager.update_equity(account_info["portfolio_value"])

        logger.info("Bot initialized successfully")
        return True

    def run_trading_cycle(self) -> None:
        """Run a single trading cycle."""
        logger.debug("Running trading cycle...")

        # Check if we need to revalidate pairs
        if self._should_revalidate():
            logger.info("Revalidating pairs...")
            self.scanner.revalidate_pairs()
            self.monitor.initialize_pairs()
            self.last_revalidation_time = datetime.now()

        # Check if we need to rescan for new pairs
        if self._should_rescan():
            logger.info("Running periodic pair scan...")
            self.scan_pairs()
            self.monitor.initialize_pairs()
            self.last_scan_time = datetime.now()

        # Check risk limits
        if not self.risk_manager.check_can_trade():
            logger.warning("Trading blocked by risk manager")
            return

        # Update prices and check for signals
        signals = self.monitor.update_prices()

        # Process signals
        for signal in signals:
            logger.info(f"Processing signal: {signal.signal_type.value}")

            # Execute the signal
            success = self.executor.execute_signal(signal)

            if success:
                # Update monitor with new position state
                if signal.signal_type == SignalType.LONG_SPREAD:
                    self.monitor.update_position_state(signal.pair_id, "long")
                elif signal.signal_type == SignalType.SHORT_SPREAD:
                    self.monitor.update_position_state(signal.pair_id, "short")
                elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT,
                                            SignalType.STOP_LOSS]:
                    self.monitor.update_position_state(signal.pair_id, None)

        # Update portfolio and risk metrics
        all_symbols = set()
        for state in self.monitor.get_all_states():
            all_symbols.add(state.symbol1)
            all_symbols.add(state.symbol2)

        if all_symbols:
            prices = self.fetcher.fetch_latest_prices(list(all_symbols))
            self.executor.update_positions(prices)

            # Update risk manager
            account = self.executor.broker.get_account_info()
            self.risk_manager.update_equity(account["portfolio_value"])

        # Save performance snapshot periodically
        self.executor.save_performance_snapshot()

    def _should_revalidate(self) -> bool:
        """Check if pairs should be revalidated."""
        if self.last_revalidation_time is None:
            return True

        elapsed = (datetime.now() - self.last_revalidation_time).days
        return elapsed >= self.revalidation_interval_days

    def _should_rescan(self) -> bool:
        """Check if we should scan for new pairs."""
        if self.last_scan_time is None:
            return True

        elapsed = (datetime.now() - self.last_scan_time).days
        return elapsed >= self.scan_interval_days

    def run(self) -> None:
        """
        Main bot loop.

        Continuously monitors spreads and executes trades.
        """
        if not self.initialize():
            logger.error("Failed to initialize bot")
            return

        logger.info("Starting main trading loop...")
        logger.info(f"Update interval: {self.update_interval} seconds")

        self.running = True

        while self.running:
            try:
                cycle_start = time.time()

                self.run_trading_cycle()

                # Log status
                summary = self.monitor.get_summary()
                portfolio = self.executor.get_portfolio_summary()

                logger.info(
                    f"Status: {summary['num_pairs']} pairs monitored, "
                    f"{portfolio['num_positions']} positions, "
                    f"Portfolio: ${portfolio['portfolio_value']:,.2f}"
                )

                # Wait for next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.update_interval - elapsed)

                if sleep_time > 0:
                    logger.debug(f"Sleeping for {sleep_time:.1f} seconds")
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}")
                time.sleep(10)  # Wait before retrying

        logger.info("Bot stopped")
        self._cleanup()

    def _cleanup(self) -> None:
        """Cleanup on shutdown."""
        logger.info("Running cleanup...")

        # Save final performance
        self.executor.save_performance_snapshot()

        # Log final statistics
        stats = self.db.get_pair_statistics()
        logger.info(f"Final Statistics:")
        logger.info(f"  Total trades: {stats['total_trades']}")
        logger.info(f"  Win rate: {stats['win_rate']:.2%}")
        logger.info(f"  Total PnL: ${stats['total_pnl']:.2f}")

        self.risk_manager.log_risk_status()

    def get_status(self) -> dict:
        """Get current bot status."""
        monitor_summary = self.monitor.get_summary()
        portfolio_summary = self.executor.get_portfolio_summary()
        risk_metrics = self.risk_manager.get_risk_metrics()
        db_stats = self.db.get_pair_statistics()

        return {
            "running": self.running,
            "monitor": monitor_summary,
            "portfolio": portfolio_summary,
            "risk": risk_metrics,
            "statistics": db_stats,
            "last_scan": self.last_scan_time,
            "last_revalidation": self.last_revalidation_time
        }

    def paper_trade(self, duration_hours: float = 1.0) -> None:
        """
        Run paper trading for a specified duration.

        Args:
            duration_hours: How long to run paper trading
        """
        logger.info(f"Starting paper trading for {duration_hours} hours")

        end_time = datetime.now() + timedelta(hours=duration_hours)

        if not self.initialize():
            logger.error("Failed to initialize for paper trading")
            return

        self.running = True

        while self.running and datetime.now() < end_time:
            try:
                self.run_trading_cycle()

                # Print status
                portfolio = self.executor.get_portfolio_summary()
                print(
                    f"\rPortfolio: ${portfolio['portfolio_value']:,.2f} | "
                    f"Positions: {portfolio['num_positions']} | "
                    f"PnL: ${portfolio['realized_pnl']:,.2f}",
                    end="", flush=True
                )

                time.sleep(self.update_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in paper trading: {e}")
                time.sleep(10)

        print()  # New line after status updates
        logger.info("Paper trading session ended")
        self._cleanup()
