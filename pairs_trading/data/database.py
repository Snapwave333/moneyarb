"""Database module for storing pairs, trades, and performance data."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json

from ..utils.config import get_config
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class Database:
    """SQLite database for pairs trading data."""

    def __init__(self, db_path: Optional[str] = None):
        config = get_config()
        if db_path is None:
            db_path = config.get("database.path", "data/pairs_trading.db")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Cointegrated pairs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol1 TEXT NOT NULL,
                    symbol2 TEXT NOT NULL,
                    cointegration_pvalue REAL,
                    correlation REAL,
                    half_life REAL,
                    hedge_ratio REAL,
                    mean_spread REAL,
                    std_spread REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(symbol1, symbol2)
                )
            """)

            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER,
                    entry_time TIMESTAMP,
                    exit_time TIMESTAMP,
                    symbol1 TEXT,
                    symbol2 TEXT,
                    entry_price1 REAL,
                    entry_price2 REAL,
                    exit_price1 REAL,
                    exit_price2 REAL,
                    quantity1 REAL,
                    quantity2 REAL,
                    entry_zscore REAL,
                    exit_zscore REAL,
                    pnl REAL,
                    status TEXT DEFAULT 'open',
                    FOREIGN KEY (pair_id) REFERENCES pairs(id)
                )
            """)

            # Performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_value REAL,
                    cash REAL,
                    positions_value REAL,
                    daily_pnl REAL,
                    total_pnl REAL,
                    num_positions INTEGER,
                    max_drawdown REAL
                )
            """)

            # Signals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pair_id INTEGER,
                    symbol1 TEXT,
                    symbol2 TEXT,
                    signal_type TEXT,
                    zscore REAL,
                    spread REAL,
                    executed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (pair_id) REFERENCES pairs(id)
                )
            """)

            conn.commit()
            logger.info("Database initialized successfully")

    def save_pair(
        self,
        symbol1: str,
        symbol2: str,
        pvalue: float,
        correlation: float,
        half_life: float,
        hedge_ratio: float,
        mean_spread: float,
        std_spread: float
    ) -> int:
        """Save or update a cointegrated pair."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO pairs
                (symbol1, symbol2, cointegration_pvalue, correlation,
                 half_life, hedge_ratio, mean_spread, std_spread, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol1, symbol2, pvalue, correlation, half_life,
                  hedge_ratio, mean_spread, std_spread, datetime.now()))
            conn.commit()
            return cursor.lastrowid

    def get_active_pairs(self) -> List[Dict[str, Any]]:
        """Get all active cointegrated pairs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pairs WHERE is_active = 1")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def save_trade(
        self,
        pair_id: int,
        symbol1: str,
        symbol2: str,
        entry_price1: float,
        entry_price2: float,
        quantity1: float,
        quantity2: float,
        entry_zscore: float
    ) -> int:
        """Save a new trade entry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades
                (pair_id, entry_time, symbol1, symbol2, entry_price1, entry_price2,
                 quantity1, quantity2, entry_zscore, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
            """, (pair_id, datetime.now(), symbol1, symbol2, entry_price1,
                  entry_price2, quantity1, quantity2, entry_zscore))
            conn.commit()
            return cursor.lastrowid

    def close_trade(
        self,
        trade_id: int,
        exit_price1: float,
        exit_price2: float,
        exit_zscore: float,
        pnl: float
    ) -> None:
        """Close an existing trade."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trades
                SET exit_time = ?, exit_price1 = ?, exit_price2 = ?,
                    exit_zscore = ?, pnl = ?, status = 'closed'
                WHERE id = ?
            """, (datetime.now(), exit_price1, exit_price2, exit_zscore, pnl, trade_id))
            conn.commit()

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE status = 'open'")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def save_performance(
        self,
        total_value: float,
        cash: float,
        positions_value: float,
        daily_pnl: float,
        total_pnl: float,
        num_positions: int,
        max_drawdown: float
    ) -> None:
        """Save performance snapshot."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance
                (total_value, cash, positions_value, daily_pnl,
                 total_pnl, num_positions, max_drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (total_value, cash, positions_value, daily_pnl,
                  total_pnl, num_positions, max_drawdown))
            conn.commit()

    def save_signal(
        self,
        pair_id: int,
        symbol1: str,
        symbol2: str,
        signal_type: str,
        zscore: float,
        spread: float
    ) -> int:
        """Save a trading signal."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals
                (pair_id, symbol1, symbol2, signal_type, zscore, spread)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pair_id, symbol1, symbol2, signal_type, zscore, spread))
            conn.commit()
            return cursor.lastrowid

    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades
                WHERE status = 'closed'
                ORDER BY exit_time DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_performance_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get performance history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM performance
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def deactivate_pair(self, pair_id: int) -> None:
        """Deactivate a pair (no longer trade it)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pairs SET is_active = 0 WHERE id = ?",
                (pair_id,)
            )
            conn.commit()

    def get_pair_statistics(self) -> Dict[str, Any]:
        """Get overall pair statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total pairs
            cursor.execute("SELECT COUNT(*) FROM pairs WHERE is_active = 1")
            active_pairs = cursor.fetchone()[0]

            # Total trades
            cursor.execute("SELECT COUNT(*) FROM trades")
            total_trades = cursor.fetchone()[0]

            # Win rate
            cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0 AND status = 'closed'")
            winning_trades = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'closed'")
            closed_trades = cursor.fetchone()[0]

            win_rate = winning_trades / closed_trades if closed_trades > 0 else 0

            # Total PnL
            cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'closed'")
            total_pnl = cursor.fetchone()[0] or 0

            return {
                "active_pairs": active_pairs,
                "total_trades": total_trades,
                "closed_trades": closed_trades,
                "winning_trades": winning_trades,
                "win_rate": win_rate,
                "total_pnl": total_pnl
            }
