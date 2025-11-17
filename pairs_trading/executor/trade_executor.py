"""
Trade execution engine for pairs trading.

Handles order placement, position management, and portfolio tracking.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..data.database import Database
from ..monitor.spread_monitor import TradingSignal, SignalType

logger = setup_logger(__name__)


@dataclass
class Position:
    """Represents a pairs trading position."""
    pair_id: int
    trade_id: int
    symbol1: str
    symbol2: str
    quantity1: float  # Positive for long, negative for short
    quantity2: float
    entry_price1: float
    entry_price2: float
    entry_zscore: float
    entry_time: datetime
    current_value: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class Order:
    """Represents a trade order."""
    symbol: str
    quantity: float  # Positive for buy, negative for sell
    order_type: str  # 'market', 'limit'
    limit_price: Optional[float] = None
    status: str = "pending"
    filled_price: Optional[float] = None
    filled_time: Optional[datetime] = None


class BrokerInterface(ABC):
    """Abstract interface for broker connections."""

    @abstractmethod
    def place_order(self, order: Order) -> str:
        """Place an order and return order ID."""
        pass

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information (cash, positions, etc.)."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, float]:
        """Get current positions."""
        pass


class PaperBroker(BrokerInterface):
    """Paper trading broker for simulation."""

    def __init__(self, initial_capital: float = 100000.0):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.portfolio_value = initial_capital
        self.orders_placed = 0

    def place_order(self, order: Order) -> str:
        """Simulate order execution."""
        self.orders_placed += 1
        order_id = f"PAPER_{self.orders_placed}"

        # Simulate market order instant fill
        if order.order_type == "market":
            # In paper trading, we assume the fill price is the current price
            # (passed via limit_price for simplicity)
            fill_price = order.limit_price if order.limit_price else 0.0

            # Update cash and positions
            cost = order.quantity * fill_price
            self.cash -= cost

            if order.symbol in self.positions:
                self.positions[order.symbol] += order.quantity
            else:
                self.positions[order.symbol] = order.quantity

            # Clean up zero positions
            if abs(self.positions.get(order.symbol, 0)) < 0.0001:
                del self.positions[order.symbol]

            order.status = "filled"
            order.filled_price = fill_price
            order.filled_time = datetime.now()

            logger.info(
                f"Paper order filled: {order.symbol} "
                f"qty={order.quantity:.2f} @ ${fill_price:.2f}"
            )

        return order_id

    def get_account_info(self) -> Dict[str, Any]:
        """Get paper account info."""
        return {
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "initial_capital": self.initial_capital,
            "num_positions": len(self.positions)
        }

    def get_positions(self) -> Dict[str, float]:
        """Get current positions."""
        return self.positions.copy()

    def update_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Update portfolio value with current prices."""
        positions_value = sum(
            qty * prices.get(symbol, 0)
            for symbol, qty in self.positions.items()
        )
        self.portfolio_value = self.cash + positions_value
        return self.portfolio_value


class TradeExecutor:
    """
    Main trade execution engine.

    Converts trading signals into actual orders and manages positions.
    """

    def __init__(self):
        self.config = get_config()
        self.db = Database()

        # Initialize broker
        broker_type = self.config.get("executor.broker", "paper")
        if broker_type == "paper":
            initial_capital = self.config.get("executor.paper_capital", 100000.0)
            self.broker = PaperBroker(initial_capital)
        else:
            # For live trading, implement AlpacaBroker, IBBroker, etc.
            raise NotImplementedError(f"Broker type '{broker_type}' not implemented")

        # Execution parameters
        self.position_sizing = self.config.get("executor.position_sizing", "percent")
        self.position_size_pct = self.config.get("executor.position_size_pct", 0.05)
        self.max_positions = self.config.get("executor.max_positions", 10)
        self.live_trading = self.config.get("executor.live_trading", False)

        # Track active positions
        self.active_positions: Dict[int, Position] = {}

        # Performance tracking
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.peak_value = self.broker.initial_capital
        self.max_drawdown = 0.0

    def execute_signal(self, signal: TradingSignal) -> bool:
        """
        Execute a trading signal.

        Args:
            signal: The trading signal to execute

        Returns:
            True if execution was successful
        """
        if not self.live_trading and not isinstance(self.broker, PaperBroker):
            logger.warning("Live trading is disabled. Signal not executed.")
            return False

        try:
            if signal.signal_type == SignalType.LONG_SPREAD:
                return self._enter_long_spread(signal)

            elif signal.signal_type == SignalType.SHORT_SPREAD:
                return self._enter_short_spread(signal)

            elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                return self._exit_position(signal)

            elif signal.signal_type == SignalType.STOP_LOSS:
                logger.warning(f"Stop loss triggered for {signal.symbol1}-{signal.symbol2}")
                return self._exit_position(signal)

            else:
                logger.warning(f"Unknown signal type: {signal.signal_type}")
                return False

        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return False

    def _enter_long_spread(self, signal: TradingSignal) -> bool:
        """
        Enter a long spread position.

        Long spread: Buy stock1, sell stock2 (short)
        Bet: Spread will increase (stock1 outperforms stock2)
        """
        if len(self.active_positions) >= self.max_positions:
            logger.warning("Maximum positions reached. Cannot enter new position.")
            return False

        if signal.pair_id in self.active_positions:
            logger.warning(f"Already have position for pair {signal.pair_id}")
            return False

        # Calculate position sizes
        qty1, qty2 = self._calculate_position_size(
            signal.price1, signal.price2, signal.hedge_ratio
        )

        # Place orders
        # Buy stock1
        order1 = Order(
            symbol=signal.symbol1,
            quantity=qty1,  # Positive = buy
            order_type="market",
            limit_price=signal.price1
        )

        # Sell stock2 (short)
        order2 = Order(
            symbol=signal.symbol2,
            quantity=-qty2,  # Negative = sell/short
            order_type="market",
            limit_price=signal.price2
        )

        # Execute orders
        order_id1 = self.broker.place_order(order1)
        order_id2 = self.broker.place_order(order2)

        # Save trade to database
        trade_id = self.db.save_trade(
            pair_id=signal.pair_id,
            symbol1=signal.symbol1,
            symbol2=signal.symbol2,
            entry_price1=signal.price1,
            entry_price2=signal.price2,
            quantity1=qty1,
            quantity2=-qty2,
            entry_zscore=signal.zscore
        )

        # Track position
        position = Position(
            pair_id=signal.pair_id,
            trade_id=trade_id,
            symbol1=signal.symbol1,
            symbol2=signal.symbol2,
            quantity1=qty1,
            quantity2=-qty2,
            entry_price1=signal.price1,
            entry_price2=signal.price2,
            entry_zscore=signal.zscore,
            entry_time=datetime.now()
        )
        self.active_positions[signal.pair_id] = position

        logger.info(
            f"Entered LONG spread: {signal.symbol1}-{signal.symbol2} "
            f"(qty1={qty1:.2f}, qty2={qty2:.2f}, z-score={signal.zscore:.2f})"
        )
        return True

    def _enter_short_spread(self, signal: TradingSignal) -> bool:
        """
        Enter a short spread position.

        Short spread: Sell stock1 (short), buy stock2
        Bet: Spread will decrease (stock2 outperforms stock1)
        """
        if len(self.active_positions) >= self.max_positions:
            logger.warning("Maximum positions reached. Cannot enter new position.")
            return False

        if signal.pair_id in self.active_positions:
            logger.warning(f"Already have position for pair {signal.pair_id}")
            return False

        # Calculate position sizes
        qty1, qty2 = self._calculate_position_size(
            signal.price1, signal.price2, signal.hedge_ratio
        )

        # Place orders
        # Sell stock1 (short)
        order1 = Order(
            symbol=signal.symbol1,
            quantity=-qty1,  # Negative = sell/short
            order_type="market",
            limit_price=signal.price1
        )

        # Buy stock2
        order2 = Order(
            symbol=signal.symbol2,
            quantity=qty2,  # Positive = buy
            order_type="market",
            limit_price=signal.price2
        )

        # Execute orders
        self.broker.place_order(order1)
        self.broker.place_order(order2)

        # Save trade to database
        trade_id = self.db.save_trade(
            pair_id=signal.pair_id,
            symbol1=signal.symbol1,
            symbol2=signal.symbol2,
            entry_price1=signal.price1,
            entry_price2=signal.price2,
            quantity1=-qty1,
            quantity2=qty2,
            entry_zscore=signal.zscore
        )

        # Track position
        position = Position(
            pair_id=signal.pair_id,
            trade_id=trade_id,
            symbol1=signal.symbol1,
            symbol2=signal.symbol2,
            quantity1=-qty1,
            quantity2=qty2,
            entry_price1=signal.price1,
            entry_price2=signal.price2,
            entry_zscore=signal.zscore,
            entry_time=datetime.now()
        )
        self.active_positions[signal.pair_id] = position

        logger.info(
            f"Entered SHORT spread: {signal.symbol1}-{signal.symbol2} "
            f"(qty1=-{qty1:.2f}, qty2={qty2:.2f}, z-score={signal.zscore:.2f})"
        )
        return True

    def _exit_position(self, signal: TradingSignal) -> bool:
        """Exit an existing position."""
        if signal.pair_id not in self.active_positions:
            logger.warning(f"No active position for pair {signal.pair_id}")
            return False

        position = self.active_positions[signal.pair_id]

        # Place closing orders (opposite of entry)
        # Close stock1 position
        order1 = Order(
            symbol=position.symbol1,
            quantity=-position.quantity1,  # Reverse the position
            order_type="market",
            limit_price=signal.price1
        )

        # Close stock2 position
        order2 = Order(
            symbol=position.symbol2,
            quantity=-position.quantity2,  # Reverse the position
            order_type="market",
            limit_price=signal.price2
        )

        # Execute orders
        self.broker.place_order(order1)
        self.broker.place_order(order2)

        # Calculate PnL
        pnl1 = position.quantity1 * (signal.price1 - position.entry_price1)
        pnl2 = position.quantity2 * (signal.price2 - position.entry_price2)
        total_pnl = pnl1 + pnl2

        # Update database
        self.db.close_trade(
            trade_id=position.trade_id,
            exit_price1=signal.price1,
            exit_price2=signal.price2,
            exit_zscore=signal.zscore,
            pnl=total_pnl
        )

        # Update tracking
        self.total_pnl += total_pnl
        self.daily_pnl += total_pnl
        del self.active_positions[signal.pair_id]

        logger.info(
            f"Closed position: {signal.symbol1}-{signal.symbol2} "
            f"PnL=${total_pnl:.2f}, z-score={signal.zscore:.2f}"
        )
        return True

    def _calculate_position_size(
        self,
        price1: float,
        price2: float,
        hedge_ratio: float
    ) -> Tuple[float, float]:
        """
        Calculate position sizes for a pairs trade.

        The position size is determined by:
        1. Available capital
        2. Position sizing method
        3. Hedge ratio (to maintain market neutrality)
        """
        account_info = self.broker.get_account_info()

        if self.position_sizing == "percent":
            # Use percentage of portfolio
            capital_for_trade = account_info["portfolio_value"] * self.position_size_pct
        else:
            # Fixed dollar amount
            capital_for_trade = 10000.0  # Default fixed amount

        # Split capital between the two legs
        # Allocate proportionally based on prices and hedge ratio
        total_cost_per_unit = price1 + hedge_ratio * price2

        # Calculate how many "units" we can buy
        units = capital_for_trade / total_cost_per_unit

        qty1 = units
        qty2 = units * hedge_ratio

        return qty1, qty2

    def update_positions(self, prices: Dict[str, float]) -> None:
        """Update unrealized PnL for all positions."""
        for pair_id, position in self.active_positions.items():
            if position.symbol1 in prices and position.symbol2 in prices:
                current_value1 = position.quantity1 * prices[position.symbol1]
                current_value2 = position.quantity2 * prices[position.symbol2]

                entry_value1 = position.quantity1 * position.entry_price1
                entry_value2 = position.quantity2 * position.entry_price2

                position.current_value = current_value1 + current_value2
                position.unrealized_pnl = (
                    (current_value1 - entry_value1) + (current_value2 - entry_value2)
                )

        # Update portfolio value
        portfolio_value = self.broker.update_portfolio_value(prices)

        # Update max drawdown
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
        drawdown = (self.peak_value - portfolio_value) / self.peak_value
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary."""
        account = self.broker.get_account_info()

        total_unrealized = sum(p.unrealized_pnl for p in self.active_positions.values())

        return {
            "cash": account["cash"],
            "portfolio_value": account["portfolio_value"],
            "num_positions": len(self.active_positions),
            "unrealized_pnl": total_unrealized,
            "realized_pnl": self.total_pnl,
            "daily_pnl": self.daily_pnl,
            "max_drawdown": self.max_drawdown,
            "total_return_pct": (
                (account["portfolio_value"] - account["initial_capital"])
                / account["initial_capital"] * 100
            )
        }

    def get_active_positions(self) -> List[Position]:
        """Get all active positions."""
        return list(self.active_positions.values())

    def reset_daily_pnl(self) -> None:
        """Reset daily PnL counter (call at start of each day)."""
        self.daily_pnl = 0.0

    def save_performance_snapshot(self) -> None:
        """Save current performance to database."""
        account = self.broker.get_account_info()
        total_unrealized = sum(p.unrealized_pnl for p in self.active_positions.values())

        self.db.save_performance(
            total_value=account["portfolio_value"],
            cash=account["cash"],
            positions_value=account["portfolio_value"] - account["cash"],
            daily_pnl=self.daily_pnl,
            total_pnl=self.total_pnl + total_unrealized,
            num_positions=len(self.active_positions),
            max_drawdown=self.max_drawdown
        )
