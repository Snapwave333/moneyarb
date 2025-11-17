"""Data fetching module for historical and real-time stock data."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import pickle

try:
    import yfinance as yf
except ImportError:
    yf = None

from ..utils.config import get_config
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DataFetcher:
    """Fetches and caches stock data from various sources."""

    def __init__(self):
        self.config = get_config()
        self.source = self.config.get("data.source", "yfinance")
        self.cache_dir = Path(self.config.get("data.cache_dir", "data/cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.lookback_days = self.config.get("data.lookback_days", 252)

    def fetch_historical_data(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical price data for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with adjusted close prices, indexed by date
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        if start_date is None:
            start_dt = datetime.now() - timedelta(days=self.lookback_days * 1.5)
            start_date = start_dt.strftime("%Y-%m-%d")

        logger.info(f"Fetching data for {len(symbols)} symbols from {start_date} to {end_date}")

        if use_cache:
            cached_data = self._load_from_cache(symbols, start_date, end_date)
            if cached_data is not None:
                logger.info("Using cached data")
                return cached_data

        if self.source == "yfinance":
            data = self._fetch_from_yfinance(symbols, start_date, end_date)
        else:
            raise ValueError(f"Unknown data source: {self.source}")

        if use_cache and data is not None:
            self._save_to_cache(data, symbols, start_date, end_date)

        return data

    def _fetch_from_yfinance(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Fetch data from Yahoo Finance."""
        if yf is None:
            raise ImportError("yfinance is not installed. Run: pip install yfinance")

        logger.info(f"Downloading data from Yahoo Finance...")

        # Download data for all symbols at once
        try:
            data = yf.download(
                symbols,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                threads=True
            )

            # Handle single vs multiple symbols
            if len(symbols) == 1:
                prices = data['Close'].to_frame(name=symbols[0])
            else:
                prices = data['Close']

            # Drop any symbols with insufficient data
            min_points = self.config.get("data.min_data_points", 200)
            valid_symbols = []
            for col in prices.columns:
                if prices[col].dropna().shape[0] >= min_points:
                    valid_symbols.append(col)
                else:
                    logger.warning(f"Dropping {col}: insufficient data points")

            prices = prices[valid_symbols]

            # Forward fill missing values (holidays, etc.)
            prices = prices.ffill().dropna()

            logger.info(f"Successfully fetched data for {len(valid_symbols)} symbols")
            return prices

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise

    def _get_cache_key(self, symbols: List[str], start_date: str, end_date: str) -> str:
        """Generate a cache key for the data."""
        symbols_hash = hash(tuple(sorted(symbols)))
        return f"data_{symbols_hash}_{start_date}_{end_date}.pkl"

    def _load_from_cache(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """Load data from cache if available and recent."""
        cache_key = self._get_cache_key(symbols, start_date, end_date)
        cache_path = self.cache_dir / cache_key

        if cache_path.exists():
            # Check if cache is less than 24 hours old
            cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
            if cache_age < 86400:  # 24 hours in seconds
                try:
                    with open(cache_path, 'rb') as f:
                        return pickle.load(f)
                except Exception as e:
                    logger.warning(f"Error loading cache: {e}")
        return None

    def _save_to_cache(
        self,
        data: pd.DataFrame,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> None:
        """Save data to cache."""
        cache_key = self._get_cache_key(symbols, start_date, end_date)
        cache_path = self.cache_dir / cache_key

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Data cached to {cache_path}")
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")

    def get_sp500_symbols(self) -> List[str]:
        """Get list of S&P 500 symbols from Wikipedia."""
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(url)
            sp500_table = tables[0]
            symbols = sp500_table['Symbol'].tolist()
            # Clean up symbols (remove dots for Yahoo Finance compatibility)
            symbols = [s.replace('.', '-') for s in symbols]
            logger.info(f"Retrieved {len(symbols)} S&P 500 symbols")
            return symbols
        except Exception as e:
            logger.error(f"Error fetching S&P 500 symbols: {e}")
            # Return a default list of major stocks
            return self._get_default_universe()

    def _get_default_universe(self) -> List[str]:
        """Return a default universe of liquid stocks."""
        return [
            # Technology
            "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "CRM", "ADBE", "ORCL",
            # Finance
            "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "USB",
            # Consumer
            "AMZN", "WMT", "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "LOW", "TJX",
            # Healthcare
            "JNJ", "UNH", "PFE", "MRK", "ABBV", "TMO", "DHR", "BMY", "LLY", "AMGN",
            # Energy
            "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO", "MPC", "OXY", "HAL",
            # Industrial
            "CAT", "DE", "BA", "HON", "UPS", "RTX", "LMT", "GE", "MMM", "EMR",
        ]

    def get_sector_symbols(self, sector: str) -> List[str]:
        """Get symbols for a specific sector."""
        sector_map = {
            "technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "CRM", "ADBE", "ORCL"],
            "finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "USB"],
            "consumer": ["AMZN", "WMT", "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "LOW", "TJX"],
            "healthcare": ["JNJ", "UNH", "PFE", "MRK", "ABBV", "TMO", "DHR", "BMY", "LLY", "AMGN"],
            "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO", "MPC", "OXY", "HAL"],
            "industrial": ["CAT", "DE", "BA", "HON", "UPS", "RTX", "LMT", "GE", "MMM", "EMR"],
        }
        return sector_map.get(sector.lower(), [])

    def fetch_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch the latest prices for given symbols."""
        if yf is None:
            raise ImportError("yfinance is not installed")

        prices = {}
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")
                if not hist.empty:
                    prices[symbol] = hist['Close'].iloc[-1]
            except Exception as e:
                logger.warning(f"Error fetching latest price for {symbol}: {e}")
        return prices

    def calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Calculate daily returns from prices."""
        return prices.pct_change().dropna()

    def calculate_log_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Calculate log returns from prices."""
        return np.log(prices / prices.shift(1)).dropna()
