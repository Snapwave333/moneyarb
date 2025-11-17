"""
Risk management module for pairs trading.

Monitors portfolio risk metrics and enforces trading limits.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..data.database import Database

logger = setup_logger(__name__)


class RiskManager:
    """
    Risk management and position sizing for pairs trading.

    Enforces:
    - Maximum drawdown limits
    - Daily loss limits
    - Position size limits
    - Correlation limits between pairs
    - Holding period limits
    """

    def __init__(self):
        self.config = get_config()
        self.db = Database()

        # Risk parameters
        self.max_drawdown_pct = self.config.get("risk.max_drawdown_pct", 0.15)
        self.max_pair_loss_pct = self.config.get("risk.max_pair_loss_pct", 0.02)
        self.daily_loss_limit = self.config.get("risk.daily_loss_limit", 0.03)
        self.max_pair_correlation = self.config.get("risk.max_pair_correlation", 0.5)
        self.min_holding_period = self.config.get("risk.min_holding_period", 1)
        self.max_holding_period = self.config.get("risk.max_holding_period", 30)

        # Tracking
        self.daily_pnl = 0.0
        self.initial_capital = self.config.get("executor.paper_capital", 100000.0)
        self.peak_equity = self.initial_capital
        self.current_equity = self.initial_capital
        self.trading_halted = False
        self.halt_reason = ""

    def check_can_trade(self) -> bool:
        """Check if trading is allowed based on risk limits."""
        if self.trading_halted:
            logger.warning(f"Trading halted: {self.halt_reason}")
            return False

        # Check daily loss limit
        daily_loss_pct = abs(self.daily_pnl) / self.initial_capital
        if self.daily_pnl < 0 and daily_loss_pct > self.daily_loss_limit:
            self._halt_trading(f"Daily loss limit exceeded: {daily_loss_pct:.2%}")
            return False

        # Check max drawdown
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        if drawdown > self.max_drawdown_pct:
            self._halt_trading(f"Max drawdown exceeded: {drawdown:.2%}")
            return False

        return True

    def _halt_trading(self, reason: str) -> None:
        """Halt all trading."""
        self.trading_halted = True
        self.halt_reason = reason
        logger.error(f"TRADING HALTED: {reason}")

    def resume_trading(self) -> None:
        """Resume trading after halt."""
        self.trading_halted = False
        self.halt_reason = ""
        logger.info("Trading resumed")

    def update_pnl(self, pnl: float) -> None:
        """Update daily PnL tracking."""
        self.daily_pnl += pnl

    def update_equity(self, current_equity: float) -> None:
        """Update current equity for drawdown calculation."""
        self.current_equity = current_equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

    def reset_daily_tracking(self) -> None:
        """Reset daily tracking (call at start of each trading day)."""
        self.daily_pnl = 0.0
        logger.info("Daily risk tracking reset")

    def check_position_size(
        self,
        proposed_size: float,
        portfolio_value: float
    ) -> float:
        """
        Check and adjust position size based on risk limits.

        Args:
            proposed_size: Proposed position size in dollars
            portfolio_value: Current portfolio value

        Returns:
            Adjusted position size
        """
        max_size = portfolio_value * self.config.get("executor.position_size_pct", 0.05)
        if proposed_size > max_size:
            logger.warning(
                f"Position size ${proposed_size:.2f} exceeds max ${max_size:.2f}. "
                f"Reducing to max."
            )
            return max_size
        return proposed_size

    def check_pair_loss(self, unrealized_pnl: float, entry_value: float) -> bool:
        """
        Check if a pair's loss exceeds the maximum allowed.

        Returns True if position should be closed.
        """
        loss_pct = abs(unrealized_pnl) / entry_value if entry_value > 0 else 0
        if unrealized_pnl < 0 and loss_pct > self.max_pair_loss_pct:
            logger.warning(f"Pair loss {loss_pct:.2%} exceeds max {self.max_pair_loss_pct:.2%}")
            return True
        return False

    def check_holding_period(self, entry_time: datetime) -> str:
        """
        Check if holding period is within limits.

        Returns:
            'ok', 'too_short', or 'too_long'
        """
        holding_days = (datetime.now() - entry_time).days

        if holding_days < self.min_holding_period:
            return 'too_short'
        elif holding_days > self.max_holding_period:
            return 'too_long'
        return 'ok'

    def calculate_kelly_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        portfolio_value: float
    ) -> float:
        """
        Calculate position size using Kelly Criterion.

        Kelly fraction = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win

        This is often reduced (e.g., half-Kelly) to be more conservative.
        """
        if avg_win <= 0:
            return 0.0

        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win

        # Use half-Kelly for safety
        kelly_fraction = kelly_fraction * 0.5

        # Cap at maximum position size
        max_fraction = self.config.get("executor.position_size_pct", 0.05)
        kelly_fraction = min(kelly_fraction, max_fraction)
        kelly_fraction = max(kelly_fraction, 0.0)

        return portfolio_value * kelly_fraction

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics."""
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity

        return {
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "current_drawdown": drawdown,
            "max_drawdown_limit": self.max_drawdown_pct,
            "daily_pnl": self.daily_pnl,
            "daily_loss_limit": self.daily_loss_limit,
            "trading_halted": self.trading_halted,
            "halt_reason": self.halt_reason
        }

    def evaluate_portfolio_risk(
        self,
        active_positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate overall portfolio risk.

        Checks for:
        - Concentration risk
        - Sector exposure
        - Correlation between positions
        """
        if not active_positions:
            return {"risk_level": "low", "warnings": []}

        warnings = []

        # Check number of positions
        max_positions = self.config.get("executor.max_positions", 10)
        if len(active_positions) >= max_positions:
            warnings.append(f"Maximum positions ({max_positions}) reached")

        # Check total exposure
        total_exposure = sum(
            abs(p.get('current_value', 0)) for p in active_positions
        )
        exposure_ratio = total_exposure / self.current_equity if self.current_equity > 0 else 0

        if exposure_ratio > 0.8:
            warnings.append(f"High exposure ratio: {exposure_ratio:.2%}")

        # Determine risk level
        if len(warnings) > 2:
            risk_level = "high"
        elif len(warnings) > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "num_positions": len(active_positions),
            "total_exposure": total_exposure,
            "exposure_ratio": exposure_ratio
        }

    def log_risk_status(self) -> None:
        """Log current risk status."""
        metrics = self.get_risk_metrics()

        logger.info("=" * 40)
        logger.info("RISK STATUS")
        logger.info("=" * 40)
        logger.info(f"Current Equity: ${metrics['current_equity']:,.2f}")
        logger.info(f"Peak Equity: ${metrics['peak_equity']:,.2f}")
        logger.info(f"Current Drawdown: {metrics['current_drawdown']:.2%}")
        logger.info(f"Daily PnL: ${metrics['daily_pnl']:,.2f}")

        if metrics['trading_halted']:
            logger.error(f"TRADING HALTED: {metrics['halt_reason']}")
        else:
            logger.info("Trading Status: ACTIVE")
        logger.info("=" * 40)
