from .schemas import Capabilities, ConfigError, Connection, ModelProfile, ProviderPreset

RULES_VERSION = "1"
PRESETS = {
    "openai": ProviderPreset(id="openai", protocols=("openai_chat",), default_endpoint="https://api.openai.com/v1"),
    "custom": ProviderPreset(id="custom", protocols=("openai_chat", "anthropic_messages", "google_genai")),
    "anthropic": ProviderPreset(
        id="anthropic", protocols=("anthropic_messages",), default_endpoint="https://api.anthropic.com"
    ),
    "gemini": ProviderPreset(
        id="gemini", protocols=("google_genai",), default_endpoint="https://generativelanguage.googleapis.com"
    ),
    "legacy": ProviderPreset(id="legacy", protocols=("openai_chat",), default_endpoint="https://api.openai.com/v1"),
}
REQUIRED = {
    "main": ("text", "tools", "streaming"),
    "small": ("text",),
    "structured": ("text", "tools", "tool_choice"),
    "structured_fast": ("text", "tools", "tool_choice"),
    "memory": ("text", "tools"),
    "compression": ("text",),
    "video_vision": ("text", "images"),
}


def resolve_connection(connection: Connection) -> Connection:
    preset = PRESETS[connection.preset]
    if connection.protocol not in preset.protocols:
        raise ConfigError("preset does not support selected protocol in this runtime version")
    endpoint = connection.endpoint or preset.default_endpoint
    if not endpoint:
        raise ConfigError("custom connection requires endpoint")
    return connection.model_copy(update={"endpoint": endpoint})


def validate_capabilities(role: str, profile: ModelProfile, *, streaming: bool = False) -> None:
    for name in (*REQUIRED[role], *(("streaming",) if streaming else ())):
        if getattr(profile.capabilities, name) is not True:
            raise ConfigError(f"{role}: required capability {name} is unsupported or undeclared")


def legacy_capabilities() -> Capabilities:
    return Capabilities(text=True, images=True, streaming=True, tools=True, tool_choice=True, source="legacy-declared")


def validate_parameters(profile: ModelProfile, connection: Connection) -> None:
    p = profile.parameters
    protocol = connection.protocol
    if protocol == "openai_chat":
        if p.thinking != "default" and connection.preset != "legacy":
            raise ConfigError("explicit thinking requires a supported provider parameter rule")
        if p.thinking_budget is not None or p.thinking == "adaptive" or profile.capabilities.reasoning_roundtrip:
            raise ConfigError("reasoning_roundtrip or thinking budget is unsupported by this OpenAI adapter")
    elif protocol == "anthropic_messages":
        if p.thinking == "on":
            if p.thinking_budget is None or p.thinking_budget < 1024 or p.thinking_budget >= (p.max_tokens or 4096):
                raise ConfigError("Anthropic thinking requires budget >= 1024 and less than max_tokens")
        elif p.thinking_budget is not None:
            raise ConfigError("Anthropic budget requires thinking on")
        if p.thinking in {"on", "adaptive"}:
            if p.temperature is not None:
                raise ConfigError("Anthropic thinking cannot override temperature")
            if profile.capabilities.tool_choice:
                raise ConfigError("Anthropic thinking does not support forced tool choice")
            if profile.capabilities.reasoning_roundtrip is not True:
                raise ConfigError("thinking requires declared reasoning_roundtrip")
    elif protocol == "google_genai":
        if p.thinking == "adaptive":
            raise ConfigError("Gemini adaptive thinking is not mapped by this adapter")
        if p.thinking == "on" and not p.thinking_budget:
            raise ConfigError("Gemini thinking on requires a positive budget")
        if p.thinking != "on" and p.thinking_budget is not None:
            raise ConfigError("Gemini budget requires thinking on")
        if p.thinking == "on" and profile.capabilities.reasoning_roundtrip is not True:
            raise ConfigError("thinking requires declared reasoning_roundtrip")
    if p.structured_method == "json_schema" and profile.capabilities.structured is not True:
        raise ConfigError("native schema requires declared structured capability")
