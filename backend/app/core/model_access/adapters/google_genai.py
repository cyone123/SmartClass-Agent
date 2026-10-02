"""Developer API only; never let SDK environment detection choose Vertex."""

from google import genai
from google.genai import types
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import (
    DUMMY_THOUGHT_SIGNATURE,
    _convert_to_parts,
    _convert_tool_message_to_parts,
)
from pydantic import model_validator

from ..messages import ProtocolHistoryMixin
from ..schemas import ConfigError, Connection, ModelProfile


class DeveloperChatModel(ProtocolHistoryMixin, ChatGoogleGenerativeAI):
    @model_validator(mode="after")
    def validate_environment(self):
        # 4.2.1's Developer branch omits vertexai=False when constructing the SDK.
        # Require an explicitly supplied client instead of changing process env.
        if self.client is None or self.client.vertexai:
            raise ValueError("explicit Developer API client required")
        return self

    def _format_tools(self, tools=None, functions=None):
        if not tools and not functions:
            return None
        declarations = []
        for tool in tools or functions:
            function = convert_to_openai_tool(tool)["function"]
            # The integration's legacy Schema converter silently drops constraints
            # such as additionalProperties/allOf. The SDK accepts JSON Schema intact.
            declarations.append(
                types.FunctionDeclaration(
                    name=function["name"],
                    description=function.get("description"),
                    parameters_json_schema=function.get("parameters", {}),
                )
            )
        return [types.Tool(function_declarations=declarations)]

    def _prepare_request(self, messages, **kwargs):
        request = super()._prepare_request(messages, **kwargs)
        exchanges = []
        for index, message in enumerate(messages):
            if isinstance(message, AIMessage) and message.tool_calls:
                results = []
                for following in messages[index + 1 :]:
                    if not isinstance(following, ToolMessage):
                        break
                    results.append(following)
                exchanges.append((message, results))
        current = None
        exchange_iter = iter(exchanges)
        for content in request.get("contents", []):
            if any(part.function_call for part in content.parts or []):
                current, results = next(exchange_iter)
                calls = [part for part in content.parts if part.function_call]
                for part, call in zip(calls, current.tool_calls, strict=True):
                    part.function_call.id = call["id"]
                # Preserve visible text alongside native thinking and tool signatures.
                blocks = (
                    current.content
                    if isinstance(current.content, list)
                    else [{"type": "text", "text": current.content}]
                )
                portable_blocks = [
                    b for b in blocks if isinstance(b, str) or b.get("type") in {"text", "thinking", "reasoning"}
                ]
                content.parts = [*_convert_to_parts(portable_blocks, model=self.model), *calls]
            elif current is not None and any(part.function_response for part in content.parts or []):
                parts = []
                calls_by_id = {call["id"]: call for call in current.tool_calls}
                for result in results:
                    converted = _convert_tool_message_to_parts(
                        result, name=calls_by_id[result.tool_call_id]["name"], model=self.model
                    )
                    for part in converted:
                        if part.function_response:
                            part.function_response.id = result.tool_call_id
                    parts.extend(converted)
                content.parts = parts
            for part in content.parts or []:
                if part.thought_signature == DUMMY_THOUGHT_SIGNATURE:
                    raise ConfigError("Gemini continuation requires an original thought signature")
        return request

    def __del__(self):
        # Transport ownership belongs to ModelFactory, not short-lived bindings.
        pass


def build_model(profile: ModelProfile, connection: Connection, *, api_key, streaming, sync_client, async_client):
    p = profile.parameters
    client = genai.Client(
        vertexai=False,
        api_key=api_key,
        http_options=types.HttpOptions(
            base_url=connection.endpoint,
            timeout=int((p.timeout or 60) * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
            httpx_client=sync_client,
            httpx_async_client=async_client,
        ),
    )
    kwargs = {}
    if p.temperature is not None:
        kwargs["temperature"] = p.temperature
    if p.max_tokens is not None:
        kwargs["max_output_tokens"] = p.max_tokens
    if p.thinking == "off":
        kwargs["thinking_budget"] = 0
    elif p.thinking == "on":
        kwargs["thinking_budget"] = p.thinking_budget
        kwargs["include_thoughts"] = True
    return DeveloperChatModel(
        model=profile.model_id,
        api_key=api_key,
        vertexai=False,
        project=None,
        location=None,
        credentials=None,
        client=client,
        timeout=p.timeout or 60,
        max_retries=1,
        **kwargs,
    )
