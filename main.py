#!/usr/bin/env python3
"""
Pairs Trading Bot - Main CLI Interface

Statistical Arbitrage System for discovering and trading cointegrated stock pairs.
"""

import click
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from pairs_trading.utils.logger import setup_logger
from pairs_trading.utils.config import get_config

logger = setup_logger("cli")


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """
    Pairs Trading Bot - Statistical Arbitrage System

    A comprehensive system for discovering cointegrated stock pairs,
    monitoring their spreads, and executing mean-reversion trades.
    """
    ctx.ensure_object(dict)
    if config:
        cfg = get_config()
        cfg.load_from_file(config)
        ctx.obj['config_path'] = config
    else:
        ctx.obj['config_path'] = None


@cli.command()
@click.option('--symbols', '-s', multiple=True, help='Specific symbols to scan')
@click.option('--sectors', multiple=True, help='Sectors to scan (technology, finance, etc.)')
@click.option('--limit', '-l', default=100, help='Max number of symbols to scan')
@click.pass_context
def scan(ctx, symbols, sectors, limit):
    """Scan for cointegrated stock pairs."""
    from pairs_trading.bot import PairsTradingBot

    click.echo("=" * 50)
    click.echo("PAIRS SCANNING")
    click.echo("=" * 50)

    bot = PairsTradingBot(ctx.obj.get('config_path'))

    if symbols:
        symbol_list = list(symbols)
    elif sectors:
        from pairs_trading.data.fetcher import DataFetcher
        fetcher = DataFetcher()
        symbol_list = []
        for sector in sectors:
            symbol_list.extend(fetcher.get_sector_symbols(sector))
    else:
        symbol_list = None  # Will use default universe

    if symbol_list:
        symbol_list = symbol_list[:limit]

    num_pairs = bot.scan_pairs(symbol_list)
    click.echo(f"\nFound {num_pairs} cointegrated pairs")

    # Show top pairs
    from pairs_trading.data.database import Database
    db = Database()
    pairs = db.get_active_pairs()[:10]

    if pairs:
        click.echo("\nTop 10 pairs by p-value:")
        click.echo("-" * 70)
        click.echo(f"{'Pair':<20} {'P-Value':<12} {'Correlation':<12} {'Half-Life':<12}")
        click.echo("-" * 70)
        for pair in pairs:
            pair_name = f"{pair['symbol1']}-{pair['symbol2']}"
            click.echo(
                f"{pair_name:<20} {pair['cointegration_pvalue']:<12.4f} "
                f"{pair['correlation']:<12.4f} {pair['half_life']:<12.1f}"
            )


@cli.command()
@click.option('--start', '-s', default='-2y', help='Start date (YYYY-MM-DD or -2y)')
@click.option('--end', '-e', default='today', help='End date (YYYY-MM-DD or today)')
@click.option('--pairs', '-p', type=int, default=10, help='Number of top pairs to test')
@click.pass_context
def backtest(ctx, start, end, pairs):
    """Run backtesting on discovered pairs."""
    from pairs_trading.backtest.backtester import PairsBacktester
    from pairs_trading.scanner.cointegration import CointegrationScanner
    from pairs_trading.data.database import Database

    click.echo("=" * 50)
    click.echo("BACKTESTING")
    click.echo("=" * 50)

    db = Database()
    active_pairs = db.get_active_pairs()

    if not active_pairs:
        click.echo("No pairs found. Run 'scan' first.")
        return

    # Convert database pairs to PairResult objects
    scanner = CointegrationScanner()
    fetcher = scanner.fetcher

    # Get symbols and fetch data
    symbols = set()
    for p in active_pairs[:pairs]:
        symbols.add(p['symbol1'])
        symbols.add(p['symbol2'])

    click.echo(f"Loading historical data for {len(symbols)} symbols...")
    prices = fetcher.fetch_historical_data(list(symbols))

    # Convert pairs for backtesting
    from pairs_trading.scanner.cointegration import PairResult
    pair_results = []
    for p in active_pairs[:pairs]:
        if p['symbol1'] in prices.columns and p['symbol2'] in prices.columns:
            result = scanner.test_pair(
                p['symbol1'], p['symbol2'],
                prices[p['symbol1']], prices[p['symbol2']]
            )
            if result.is_valid:
                pair_results.append(result)

    click.echo(f"Backtesting {len(pair_results)} pairs...")

    # Run backtest
    backtester = PairsBacktester()
    result = backtester.run_backtest(pair_results, start, end)

    # Print results
    backtester.print_results(result)


@cli.command()
@click.option('--duration', '-d', default=1.0, help='Duration in hours')
@click.pass_context
def paper(ctx, duration):
    """Run paper trading simulation."""
    from pairs_trading.bot import PairsTradingBot

    click.echo("=" * 50)
    click.echo("PAPER TRADING")
    click.echo("=" * 50)
    click.echo(f"Duration: {duration} hours")
    click.echo("Press Ctrl+C to stop\n")

    bot = PairsTradingBot(ctx.obj.get('config_path'))
    bot.paper_trade(duration)


@cli.command()
@click.pass_context
def run(ctx):
    """Run the live trading bot."""
    from pairs_trading.bot import PairsTradingBot

    config = get_config()
    if not config.get("executor.live_trading", False):
        click.echo("WARNING: Live trading is disabled in config")
        click.echo("Set executor.live_trading to true in config to enable")

        if not click.confirm("Continue in paper trading mode?"):
            return

    click.echo("=" * 50)
    click.echo("PAIRS TRADING BOT")
    click.echo("=" * 50)
    click.echo("Press Ctrl+C to stop\n")

    bot = PairsTradingBot(ctx.obj.get('config_path'))
    bot.run()


@cli.command()
@click.pass_context
def status(ctx):
    """Show current bot and portfolio status."""
    from pairs_trading.data.database import Database
    from pairs_trading.executor.trade_executor import TradeExecutor

    click.echo("=" * 50)
    click.echo("STATUS")
    click.echo("=" * 50)

    db = Database()

    # Pair statistics
    stats = db.get_pair_statistics()
    click.echo("\nPair Statistics:")
    click.echo(f"  Active Pairs: {stats['active_pairs']}")
    click.echo(f"  Total Trades: {stats['total_trades']}")
    click.echo(f"  Closed Trades: {stats['closed_trades']}")
    click.echo(f"  Win Rate: {stats['win_rate']:.2%}")
    click.echo(f"  Total PnL: ${stats['total_pnl']:,.2f}")

    # Open positions
    open_trades = db.get_open_trades()
    click.echo(f"\nOpen Positions: {len(open_trades)}")
    if open_trades:
        for trade in open_trades:
            click.echo(f"  {trade['symbol1']}-{trade['symbol2']}")

    # Recent performance
    perf = db.get_performance_history(limit=1)
    if perf:
        latest = perf[0]
        click.echo(f"\nLatest Performance Snapshot:")
        click.echo(f"  Total Value: ${latest['total_value']:,.2f}")
        click.echo(f"  Cash: ${latest['cash']:,.2f}")
        click.echo(f"  Positions Value: ${latest['positions_value']:,.2f}")
        click.echo(f"  Max Drawdown: {latest['max_drawdown']:.2%}")


@cli.command()
@click.option('--limit', '-l', default=20, help='Number of trades to show')
@click.pass_context
def history(ctx, limit):
    """Show trade history."""
    from pairs_trading.data.database import Database

    click.echo("=" * 50)
    click.echo("TRADE HISTORY")
    click.echo("=" * 50)

    db = Database()
    trades = db.get_trade_history(limit)

    if not trades:
        click.echo("No trade history found.")
        return

    click.echo(f"\n{'Pair':<20} {'Entry':<12} {'Exit':<12} {'PnL':<12} {'Status':<10}")
    click.echo("-" * 70)

    for trade in trades:
        pair = f"{trade['symbol1']}-{trade['symbol2']}"
        entry_date = trade['entry_time'][:10] if trade['entry_time'] else "N/A"
        exit_date = trade['exit_time'][:10] if trade['exit_time'] else "N/A"
        pnl = trade['pnl'] if trade['pnl'] else 0
        pnl_str = f"${pnl:,.2f}"
        if pnl > 0:
            pnl_str = click.style(pnl_str, fg='green')
        elif pnl < 0:
            pnl_str = click.style(pnl_str, fg='red')

        click.echo(f"{pair:<20} {entry_date:<12} {exit_date:<12} {pnl_str:<12} {trade['status']:<10}")


@cli.command()
@click.pass_context
def revalidate(ctx):
    """Revalidate existing pairs for cointegration."""
    from pairs_trading.scanner.cointegration import CointegrationScanner

    click.echo("=" * 50)
    click.echo("REVALIDATING PAIRS")
    click.echo("=" * 50)

    scanner = CointegrationScanner()
    valid_pairs = scanner.revalidate_pairs()

    click.echo(f"\n{len(valid_pairs)} pairs are still valid")


@cli.command()
@click.argument('symbol1')
@click.argument('symbol2')
@click.pass_context
def test_pair(ctx, symbol1, symbol2):
    """Test a specific pair for cointegration."""
    from pairs_trading.scanner.cointegration import CointegrationScanner
    from pairs_trading.data.fetcher import DataFetcher

    click.echo(f"Testing pair: {symbol1}-{symbol2}")

    fetcher = DataFetcher()
    scanner = CointegrationScanner()

    # Fetch data
    prices = fetcher.fetch_historical_data([symbol1, symbol2])

    if symbol1 not in prices.columns or symbol2 not in prices.columns:
        click.echo(f"Error: Could not fetch data for {symbol1} or {symbol2}")
        return

    # Test pair
    result = scanner.test_pair(symbol1, symbol2, prices[symbol1], prices[symbol2])

    click.echo("\n" + "=" * 50)
    click.echo("COINTEGRATION TEST RESULTS")
    click.echo("=" * 50)
    click.echo(f"Symbol 1: {result.symbol1}")
    click.echo(f"Symbol 2: {result.symbol2}")
    click.echo(f"Cointegration P-Value: {result.coint_pvalue:.4f}")
    click.echo(f"ADF P-Value: {result.adf_pvalue:.4f}")
    click.echo(f"Correlation: {result.correlation:.4f}")
    click.echo(f"Hedge Ratio: {result.hedge_ratio:.4f}")
    click.echo(f"Half-Life: {result.half_life:.1f} days")
    click.echo(f"Mean Spread: {result.mean_spread:.4f}")
    click.echo(f"Std Spread: {result.std_spread:.4f}")

    if result.is_valid:
        click.echo(click.style("\nPAIR IS VALID FOR TRADING", fg='green'))
    else:
        click.echo(click.style("\nPAIR IS NOT VALID", fg='red'))


@cli.command()
@click.pass_context
def init_db(ctx):
    """Initialize/reset the database."""
    from pairs_trading.data.database import Database

    if click.confirm("This will reset the database. Continue?"):
        db = Database()
        click.echo("Database initialized successfully")


if __name__ == "__main__":
    cli()
