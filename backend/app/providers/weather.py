"""Phase 9: weather provider abstraction.

ATLAS's LLM layer already has a clean provider-abstraction precedent (see
app/providers/base.py + app/providers/factory.py: an ABC, a settings-driven
factory, and a MockProvider default for local/offline use). Weather needs
the exact same shape for the exact same reason - the backend has no
built-in weather data source and shouldn't fabricate one.

There is deliberately no "real" provider implementation wired in yet: doing
that would mean either (a) hardcoding a specific paid API's request/response
shape no one has configured, or (b) fabricating weather data, both of which
this project's own coding standards explicitly rule out ("never fabricate",
"no fake production code"). What's here is the honest middle ground this
codebase already uses elsewhere for an unfinished integration point (see
app/providers/base.py's `get_embedding` - "on the interface as a
placeholder"): the interface is real and ready, the default implementation
says plainly that it isn't configured, and wiring in a real API (e.g.
OpenWeatherMap) later is a matter of implementing WeatherProvider and
pointing WEATHER_PROVIDER at it - no other code needs to change, by the
same factory-swap pattern ProviderFactory already uses for LLMs.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from app.core.config import settings


@dataclass
class WeatherResult:
    location: str
    summary: str
    temperature_c: Optional[float] = None


class WeatherProvider(ABC):
    @abstractmethod
    async def get_current_weather(self, location: str) -> WeatherResult:
        raise NotImplementedError


class UnconfiguredWeatherProvider(WeatherProvider):
    """Default provider: no weather API is configured. Raises rather than
    returning fabricated data - WeatherSkill turns this into an honest,
    user-visible "not configured" ToolResult (see app/skills/weather_skill.py)
    instead of the LLM ever seeing something that looks like real weather.
    """

    async def get_current_weather(self, location: str) -> WeatherResult:
        raise NotImplementedError(
            "No weather provider is configured for this ATLAS instance. "
            "Set WEATHER_PROVIDER (and any provider-specific API key) in "
            "app/core/config.py / the environment, then implement a "
            "WeatherProvider subclass and register it in "
            "WeatherProviderFactory.create() to enable real weather data."
        )


class WeatherProviderFactory:
    """Mirrors app/providers/factory.py's ProviderFactory shape exactly -
    settings-driven, single switch point, defaults to the honest
    "unconfigured" implementation rather than a mock that invents data."""

    @staticmethod
    def create() -> WeatherProvider:
        provider_name = settings.WEATHER_PROVIDER
        if provider_name == "unconfigured":
            return UnconfiguredWeatherProvider()
        # Future real providers register here, e.g.:
        # if provider_name == "openweathermap":
        #     return OpenWeatherMapProvider(api_key=settings.WEATHER_API_KEY)
        raise ValueError(f"Unknown WEATHER_PROVIDER '{provider_name}'")
