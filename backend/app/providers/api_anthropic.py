import anthropic

from app.providers.base import Provider, ProviderConfigError, ProviderError

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096


class AnthropicApiProvider(Provider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def complete(self, prompt: str) -> str:
        client = anthropic.Anthropic(api_key=self._api_key)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderConfigError(str(exc)) from exc
        except anthropic.APIError as exc:
            raise ProviderError(str(exc)) from exc

        return "".join(block.text for block in response.content if block.type == "text").strip()
