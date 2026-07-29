from typing import Iterator

import openai

from app.providers.base import Provider, ProviderConfigError, ProviderError

MODEL = "gpt-4o"


class OpenAiApiProvider(Provider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def complete(self, prompt: str) -> str:
        client = openai.OpenAI(api_key=self._api_key)

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
        except openai.AuthenticationError as exc:
            raise ProviderConfigError(str(exc)) from exc
        except openai.APIError as exc:
            raise ProviderError(str(exc)) from exc

        return (response.choices[0].message.content or "").strip()

    def stream_complete(self, prompt: str) -> Iterator[str]:
        client = openai.OpenAI(api_key=self._api_key)

        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except openai.AuthenticationError as exc:
            raise ProviderConfigError(str(exc)) from exc
        except openai.APIError as exc:
            raise ProviderError(str(exc)) from exc
