"""
Cointegration scanner for discovering statistically valid trading pairs.

This module implements the Engle-Granger cointegration test and other
statistical methods to identify pairs suitable for statistical arbitrage.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional
from itertools import combinations
from dataclasses import dataclass
import warnings

try:
    from statsmodels.tsa.stattools import coint, adfuller
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools.tools import add_constant
except ImportError:
    raise ImportError("statsmodels is required. Run: pip install statsmodels")

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..data.fetcher import DataFetcher
from ..data.database import Database

logger = setup_logger(__name__)


@dataclass
class PairResult:
    """Results of cointegration analysis for a pair."""
    symbol1: str
    symbol2: str
    coint_pvalue: float
    correlation: float
    hedge_ratio: float
    half_life: float
    mean_spread: float
    std_spread: float
    adf_pvalue: float
    is_valid: bool


class CointegrationScanner:
    """
    Scanner for finding cointegrated stock pairs.

    Uses the Engle-Granger two-step method:
    1. Test for cointegration using statistical tests
    2. Calculate the optimal hedge ratio
    3. Verify the spread is mean-reverting
    """

    def __init__(self):
        self.config = get_config()
        self.fetcher = DataFetcher()
        self.db = Database()

        # Scanner parameters
        self.significance_level = self.config.get("scanner.significance_level", 0.05)
        self.min_correlation = self.config.get("scanner.min_correlation", 0.7)
        self.max_pvalue = self.config.get("scanner.max_pvalue", 0.05)
        self.max_pairs = self.config.get("scanner.max_pairs", 50)

    def scan_universe(
        self,
        symbols: Optional[List[str]] = None,
        prices: Optional[pd.DataFrame] = None
    ) -> List[PairResult]:
        """
        Scan a universe of stocks for cointegrated pairs.

        Args:
            symbols: List of stock symbols to scan
            prices: Pre-fetched price data (optional)

        Returns:
            List of valid cointegrated pairs
        """
        if symbols is None:
            symbols = self.config.get("scanner.universe", [])
            if not symbols:
                symbols = self.fetcher.get_sp500_symbols()[:100]  # Limit for performance

        logger.info(f"Scanning {len(symbols)} symbols for cointegrated pairs")

        # Fetch historical data if not provided
        if prices is None:
            prices = self.fetcher.fetch_historical_data(symbols)

        # Filter to only symbols we have data for
        available_symbols = [s for s in symbols if s in prices.columns]
        logger.info(f"Data available for {len(available_symbols)} symbols")

        # Generate all possible pairs
        pairs = list(combinations(available_symbols, 2))
        total_pairs = len(pairs)
        logger.info(f"Testing {total_pairs} possible pairs")

        valid_pairs = []
        tested = 0

        for symbol1, symbol2 in pairs:
            tested += 1
            if tested % 100 == 0:
                logger.info(f"Progress: {tested}/{total_pairs} pairs tested")

            try:
                result = self.test_pair(
                    symbol1, symbol2,
                    prices[symbol1], prices[symbol2]
                )

                if result.is_valid:
                    valid_pairs.append(result)
                    logger.info(
                        f"Valid pair found: {symbol1}-{symbol2} "
                        f"(p-value: {result.coint_pvalue:.4f}, "
                        f"half-life: {result.half_life:.1f} days)"
                    )

            except Exception as e:
                logger.warning(f"Error testing {symbol1}-{symbol2}: {e}")
                continue

        # Sort by p-value and limit to max_pairs
        valid_pairs.sort(key=lambda x: x.coint_pvalue)
        valid_pairs = valid_pairs[:self.max_pairs]

        logger.info(f"Found {len(valid_pairs)} valid cointegrated pairs")
        return valid_pairs

    def test_pair(
        self,
        symbol1: str,
        symbol2: str,
        prices1: pd.Series,
        prices2: pd.Series
    ) -> PairResult:
        """
        Test a single pair for cointegration.

        Args:
            symbol1: First stock symbol
            symbol2: Second stock symbol
            prices1: Price series for first stock
            prices2: Price series for second stock

        Returns:
            PairResult with test statistics
        """
        # Align the series
        prices1, prices2 = prices1.align(prices2, join='inner')

        # Calculate correlation
        correlation = prices1.corr(prices2)

        # Quick filter: skip if correlation is too low
        if abs(correlation) < self.min_correlation:
            return PairResult(
                symbol1=symbol1,
                symbol2=symbol2,
                coint_pvalue=1.0,
                correlation=correlation,
                hedge_ratio=0.0,
                half_life=0.0,
                mean_spread=0.0,
                std_spread=0.0,
                adf_pvalue=1.0,
                is_valid=False
            )

        # Perform Engle-Granger cointegration test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coint_stat, coint_pvalue, crit_values = coint(prices1, prices2)

        # Calculate hedge ratio using OLS regression
        hedge_ratio = self._calculate_hedge_ratio(prices1, prices2)

        # Calculate the spread
        spread = prices1 - hedge_ratio * prices2

        # Test if spread is stationary (ADF test)
        adf_result = adfuller(spread, maxlag=1)
        adf_pvalue = adf_result[1]

        # Calculate half-life of mean reversion
        half_life = self._calculate_half_life(spread)

        # Calculate spread statistics
        mean_spread = spread.mean()
        std_spread = spread.std()

        # Determine if pair is valid
        is_valid = (
            coint_pvalue < self.max_pvalue and
            adf_pvalue < self.significance_level and
            half_life > 1 and  # At least 1 day
            half_life < 120 and  # Not more than ~6 months
            abs(correlation) >= self.min_correlation
        )

        return PairResult(
            symbol1=symbol1,
            symbol2=symbol2,
            coint_pvalue=coint_pvalue,
            correlation=correlation,
            hedge_ratio=hedge_ratio,
            half_life=half_life,
            mean_spread=mean_spread,
            std_spread=std_spread,
            adf_pvalue=adf_pvalue,
            is_valid=is_valid
        )

    def _calculate_hedge_ratio(
        self,
        prices1: pd.Series,
        prices2: pd.Series
    ) -> float:
        """
        Calculate the optimal hedge ratio using OLS regression.

        The hedge ratio tells us how many shares of stock2 to hold
        for each share of stock1.
        """
        # Add constant for regression
        X = add_constant(prices2.values)
        y = prices1.values

        model = OLS(y, X).fit()
        hedge_ratio = model.params[1]

        return hedge_ratio

    def _calculate_half_life(self, spread: pd.Series) -> float:
        """
        Calculate the half-life of mean reversion for the spread.

        This tells us how quickly the spread reverts to its mean,
        which is crucial for timing entries and exits.
        """
        # Lag the spread
        spread_lag = spread.shift(1)
        spread_ret = spread - spread_lag

        # Remove NaN
        spread_lag = spread_lag.iloc[1:]
        spread_ret = spread_ret.iloc[1:]

        # Regress spread returns on lagged spread
        X = add_constant(spread_lag.values)
        y = spread_ret.values

        model = OLS(y, X).fit()
        lambda_param = model.params[1]

        # Half-life formula
        if lambda_param >= 0:
            return float('inf')  # Not mean-reverting

        half_life = -np.log(2) / lambda_param
        return half_life

    def save_pairs_to_db(self, pairs: List[PairResult]) -> None:
        """Save discovered pairs to the database."""
        for pair in pairs:
            self.db.save_pair(
                symbol1=pair.symbol1,
                symbol2=pair.symbol2,
                pvalue=pair.coint_pvalue,
                correlation=pair.correlation,
                half_life=pair.half_life,
                hedge_ratio=pair.hedge_ratio,
                mean_spread=pair.mean_spread,
                std_spread=pair.std_spread
            )
        logger.info(f"Saved {len(pairs)} pairs to database")

    def revalidate_pairs(self) -> List[PairResult]:
        """
        Re-test existing pairs to ensure they're still cointegrated.

        Cointegration can break down over time, so periodic revalidation
        is important.
        """
        active_pairs = self.db.get_active_pairs()
        logger.info(f"Revalidating {len(active_pairs)} active pairs")

        # Get all unique symbols
        symbols = set()
        for pair in active_pairs:
            symbols.add(pair['symbol1'])
            symbols.add(pair['symbol2'])

        # Fetch fresh data
        prices = self.fetcher.fetch_historical_data(list(symbols), use_cache=False)

        valid_pairs = []
        for pair_data in active_pairs:
            symbol1 = pair_data['symbol1']
            symbol2 = pair_data['symbol2']

            if symbol1 not in prices.columns or symbol2 not in prices.columns:
                logger.warning(f"Missing data for {symbol1}-{symbol2}, deactivating")
                self.db.deactivate_pair(pair_data['id'])
                continue

            result = self.test_pair(
                symbol1, symbol2,
                prices[symbol1], prices[symbol2]
            )

            if result.is_valid:
                valid_pairs.append(result)
                # Update the pair in database
                self.db.save_pair(
                    symbol1=result.symbol1,
                    symbol2=result.symbol2,
                    pvalue=result.coint_pvalue,
                    correlation=result.correlation,
                    half_life=result.half_life,
                    hedge_ratio=result.hedge_ratio,
                    mean_spread=result.mean_spread,
                    std_spread=result.std_spread
                )
            else:
                logger.warning(
                    f"Pair {symbol1}-{symbol2} is no longer cointegrated, deactivating"
                )
                self.db.deactivate_pair(pair_data['id'])

        logger.info(f"{len(valid_pairs)} pairs still valid out of {len(active_pairs)}")
        return valid_pairs

    def get_pair_statistics(self, pairs: List[PairResult]) -> Dict[str, Any]:
        """Get summary statistics for discovered pairs."""
        if not pairs:
            return {}

        pvalues = [p.coint_pvalue for p in pairs]
        correlations = [p.correlation for p in pairs]
        half_lives = [p.half_life for p in pairs if p.half_life < float('inf')]

        return {
            "num_pairs": len(pairs),
            "avg_pvalue": np.mean(pvalues),
            "min_pvalue": np.min(pvalues),
            "max_pvalue": np.max(pvalues),
            "avg_correlation": np.mean(correlations),
            "avg_half_life": np.mean(half_lives) if half_lives else 0,
            "min_half_life": np.min(half_lives) if half_lives else 0,
            "max_half_life": np.max(half_lives) if half_lives else 0,
        }
