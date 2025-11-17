"""Configuration management for the pairs trading bot."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Configuration manager that loads settings from YAML files."""

    _instance: Optional['Config'] = None
    _settings: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._settings:
            self._load_default_config()

    def _load_default_config(self) -> None:
        """Load the default configuration file."""
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "settings.yaml"
        if config_path.exists():
            self.load_from_file(str(config_path))

    def load_from_file(self, filepath: str) -> None:
        """Load configuration from a YAML file."""
        with open(filepath, 'r') as f:
            self._settings = yaml.safe_load(f)
        self._expand_env_vars(self._settings)

    def _expand_env_vars(self, config: Dict[str, Any]) -> None:
        """Recursively expand environment variables in config values."""
        for key, value in config.items():
            if isinstance(value, dict):
                self._expand_env_vars(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                config[key] = os.getenv(env_var, "")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        keys = key.split(".")
        value = self._settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot notation."""
        keys = key.split(".")
        config = self._settings
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration settings."""
        return self._settings.copy()

    def update(self, new_settings: Dict[str, Any]) -> None:
        """Update settings with new values."""
        self._deep_update(self._settings, new_settings)

    def _deep_update(self, base: Dict, updates: Dict) -> None:
        """Recursively update nested dictionaries."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def save_to_file(self, filepath: str) -> None:
        """Save current configuration to a YAML file."""
        with open(filepath, 'w') as f:
            yaml.dump(self._settings, f, default_flow_style=False, sort_keys=False)


def get_config() -> Config:
    """Get the global configuration instance."""
    return Config()
