"""Phase 9: WeatherSkill.

Recognizes weather questions ATLAS previously had zero capability to
answer at all (see tests/test_device_action_endpoint.py's
"What's the weather usually like in April?" case, which pre-Phase-9 simply
fell through to the LLM with no context and no honest disclaimer). This
skill doesn't invent an answer either - it calls WeatherProviderFactory
(see app/providers/weather.py) and, since no real provider is configured
by default, returns a clear, honest "not configured" result that flows
into the prompt as a failed tool result (see PromptBuilder - failed tool
results are shown to the LLM, not hidden), so the model tells the user the
truth instead of guessing at a forecast.
"""
import re
from typing import Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.providers.weather import WeatherProviderFactory

_WEATHER_PATTERN = re.compile(
    r"\bweather\b|\bforecast\b|\bis it (?:going to |gonna )?rain\b|\btemperature outside\b",
    re.IGNORECASE,
)
_LOCATION_PATTERN = re.compile(r"\b(?:in|at|near) ([A-Z][A-Za-z\s]{2,30})", re.UNICODE)


@register_skill
class WeatherSkill(Skill):
    name = "weather"
    description = "Answers weather questions via a pluggable WeatherProvider (unconfigured by default)."

    def match(self, message: str) -> Optional[SkillMatch]:
        if _WEATHER_PATTERN.search(message):
            location_match = _LOCATION_PATTERN.search(message)
            location = location_match.group(1).strip() if location_match else "your area"
            return SkillMatch(kwargs={"location": location}, confidence=0.75)
        return None

    async def run(self, location: str = "your area", **kwargs) -> ToolResult:
        provider = WeatherProviderFactory.create()
        try:
            result = await provider.get_current_weather(location)
            return ToolResult(
                tool_name=self.name, success=True,
                output=f"{result.summary} in {result.location}.",
            )
        except NotImplementedError as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
