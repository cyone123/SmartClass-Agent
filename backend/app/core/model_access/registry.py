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
    "openrouter": ProviderPreset(
        id="openrouter",
        protocols=("openai_chat",),
        default_endpoint="https://openrouter.ai/api/v1",
        capabilities=Capabilities(
            text=True,
            streaming=True,
            tools=True,
            tool_choice=True,
            source="preset",
            verification="declared",
        ),
    ),
    "deepseek": ProviderPreset(
        id="deepseek",
        protocols=("openai_chat",),
        default_endpoint="https://api.deepseek.com",
        capabilities=Capabilities(
            text=True,
            streaming=True,
            tools=True,
            tool_choice=True,
            structured=True,
            reasoning_roundtrip=True,
            source="preset",
            verification="declared",
        ),
    ),
    "zhipu": ProviderPreset(
        id="zhipu",
        protocols=("openai_chat",),
        default_endpoint="https://open.bigmodel.cn/api/paas/v4/",
        capabilities=Capabilities(
            text=True,
            streaming=True,
            tools=True,
            tool_choice=True,
            structured=True,
            reasoning_roundtrip=True,
            source="preset",
            verification="declared",
        ),
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


def public_preset_catalog() -> list[dict]:
    """Return form metadata without endpoints, credentials or provider-private values."""
    return [
        {
            "id": preset.id,
            "protocols": list(preset.protocols),
            "credential_fields": list(preset.credential_fields),
            "credential_source": preset.credential_source,
            "endpoint_configurable": True,
            "parameter_schema": preset.parameter_schema(),
            "capabilities": preset.capabilities.model_dump(mode="json"),
            "capability_rules_version": preset.capability_rules_version,
        }
        for preset in PRESETS.values()
    ]


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
        if p.provider_routing is not None and connection.preset != "openrouter":
            raise ConfigError("provider routing is only supported by the OpenRouter preset")
        if p.thinking != "default" and connection.preset not in {"legacy", "openrouter", "deepseek", "zhipu"}:
            raise ConfigError("explicit thinking requires a supported provider parameter rule")
        if p.thinking_budget is not None:
            raise ConfigError("thinking budget is unsupported by this OpenAI adapter")
        if p.thinking == "adaptive":
            raise ConfigError("adaptive thinking is unsupported by this OpenAI adapter")
        if p.reasoning_effort is not None and connection.preset not in {"openrouter", "deepseek"}:
            raise ConfigError("reasoning effort is unsupported by the selected provider preset")
        if profile.capabilities.reasoning_roundtrip and connection.preset not in {"deepseek", "zhipu"}:
            raise ConfigError("reasoning_roundtrip or thinking budget is unsupported by this OpenAI adapter")
        if connection.preset == "deepseek" and p.thinking == "on":
            if profile.capabilities.reasoning_roundtrip is not True:
                raise ConfigError("DeepSeek thinking requires declared reasoning_roundtrip")
            if p.temperature is not None:
                raise ConfigError("DeepSeek thinking cannot override temperature")
            if profile.capabilities.tool_choice:
                raise ConfigError("DeepSeek thinking does not support forced tool choice")
        if connection.preset == "zhipu" and p.thinking == "on" and profile.capabilities.reasoning_roundtrip is not True:
            raise ConfigError("Zhipu thinking requires declared reasoning_roundtrip")
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
