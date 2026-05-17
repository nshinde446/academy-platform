from abc import ABC, abstractmethod


class PluginBase(ABC):
    """Base class for all platform plugins."""

    @abstractmethod
    def on_load(self):
        """Called when the plugin is loaded/enabled."""

    @abstractmethod
    def on_unload(self):
        """Called when the plugin is unloaded/disabled."""

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_version(self) -> str:
        return "0.0.0"


class ConfigHelper:
    """Helper for plugins to read their configuration."""

    def __init__(self, config: dict[str, str]):
        self._config = config

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._config.get(key, default)

    def require(self, key: str) -> str:
        val = self._config.get(key)
        if val is None:
            raise ValueError(f"Required config key missing: {key}")
        return val


class EventHelper:
    """Helper for plugins to interact with events."""

    @staticmethod
    def parse_event_data(data: dict) -> dict:
        return {
            "event_type": data.get("event_type", ""),
            "branch_id": data.get("branch_id"),
            "metadata": data.get("metadata", {}),
        }


class APIClient:
    """Helper for plugins to call core platform APIs."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url

    @property
    def base_url(self) -> str:
        return self._base_url
