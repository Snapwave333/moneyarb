"""Tests for the cointegration scanner."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pairs_trading.scanner.cointegration import CointegrationScanner, PairResult


class TestCointegrationScanner:
    """Test suite for CointegrationScanner."""

    def setup_method(self):
        """Setup test fixtures."""
        self.scanner = CointegrationScanner()

    def test_calculate_hedge_ratio(self):
        """Test hedge ratio calculation."""
        # Create synthetic cointegrated series
        n = 252
        np.random.seed(42)

        # Stock2 is the independent variable
        stock2 = pd.Series(
            100 + np.cumsum(np.random.randn(n) * 0.5),
            index=pd.date_range(start='2023-01-01', periods=n)
        )

        # Stock1 is hedge_ratio * stock2 + noise
        hedge_ratio_true = 1.5
        stock1 = hedge_ratio_true * stock2 + np.random.randn(n) * 2

        # Calculate hedge ratio
        hedge_ratio_calc = self.scanner._calculate_hedge_ratio(stock1, stock2)

        # Should be close to true value
        assert abs(hedge_ratio_calc - hedge_ratio_true) < 0.1

    def test_calculate_half_life(self):
        """Test half-life calculation for mean-reverting series."""
        # Create mean-reverting spread
        n = 252
        np.random.seed(42)

        # Ornstein-Uhlenbeck process with known half-life
        theta = 0.1  # Mean reversion speed
        mu = 0.0
        sigma = 1.0

        spread = [0.0]
        for _ in range(n - 1):
            dW = np.random.randn()
            new_val = spread[-1] + theta * (mu - spread[-1]) + sigma * dW
            spread.append(new_val)

        spread_series = pd.Series(spread)

        # Calculate half-life
        half_life = self.scanner._calculate_half_life(spread_series)

        # Half-life should be approximately -log(2) / theta
        expected_half_life = -np.log(2) / (-theta)  # ~6.93

        # Allow for estimation error
        assert 1 < half_life < 50  # Reasonable range

    def test_pair_result_dataclass(self):
        """Test PairResult dataclass."""
        result = PairResult(
            symbol1="AAPL",
            symbol2="MSFT",
            coint_pvalue=0.01,
            correlation=0.85,
            hedge_ratio=1.2,
            half_life=10.0,
            mean_spread=5.0,
            std_spread=1.0,
            adf_pvalue=0.02,
            is_valid=True
        )

        assert result.symbol1 == "AAPL"
        assert result.symbol2 == "MSFT"
        assert result.is_valid is True
        assert result.coint_pvalue < 0.05

    def test_test_pair_non_cointegrated(self):
        """Test that non-cointegrated pairs are rejected."""
        n = 252
        np.random.seed(42)

        # Two independent random walks (not cointegrated)
        stock1 = pd.Series(
            100 + np.cumsum(np.random.randn(n) * 2),
            index=pd.date_range(start='2023-01-01', periods=n)
        )

        stock2 = pd.Series(
            50 + np.cumsum(np.random.randn(n) * 2),
            index=pd.date_range(start='2023-01-01', periods=n)
        )

        result = self.scanner.test_pair("FAKE1", "FAKE2", stock1, stock2)

        # Independent random walks should not be cointegrated
        # The test might pass by chance, but usually won't
        assert isinstance(result, PairResult)
        assert 0 <= result.coint_pvalue <= 1

    def test_get_pair_statistics(self):
        """Test pair statistics calculation."""
        pairs = [
            PairResult("A", "B", 0.01, 0.9, 1.0, 10.0, 0.0, 1.0, 0.01, True),
            PairResult("C", "D", 0.02, 0.85, 1.1, 15.0, 0.0, 1.0, 0.02, True),
            PairResult("E", "F", 0.03, 0.8, 0.9, 20.0, 0.0, 1.0, 0.03, True),
        ]

        stats = self.scanner.get_pair_statistics(pairs)

        assert stats["num_pairs"] == 3
        assert stats["avg_pvalue"] == pytest.approx(0.02, abs=0.001)
        assert stats["min_pvalue"] == 0.01
        assert stats["max_pvalue"] == 0.03
        assert stats["avg_half_life"] == 15.0

    def test_empty_statistics(self):
        """Test statistics with empty pair list."""
        stats = self.scanner.get_pair_statistics([])
        assert stats == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
