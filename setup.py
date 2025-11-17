"""Setup configuration for pairs trading bot."""

from setuptools import setup, find_packages

setup(
    name="pairs-trading-bot",
    version="1.0.0",
    description="Statistical Arbitrage Trading Bot",
    author="MoneyArb Team",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scipy>=1.10.0",
        "statsmodels>=0.14.0",
        "yfinance>=0.2.28",
        "click>=8.1.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pairs-bot=main:cli",
        ],
    },
    python_requires=">=3.8",
)
