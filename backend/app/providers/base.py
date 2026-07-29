from abc import ABC, abstractmethod
from typing import Iterator


class ProviderError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProviderMissingError(ProviderError):
    pass


class ProviderConfigError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class Provider(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        ...

    def stream_complete(self, prompt: str) -> Iterator[str]:
        """Default fallback: no incremental streaming, yield the full response as one chunk.

        Overridden by providers with native SDK streaming (api_anthropic, api_openai).
        CLI providers inherit this default until real subprocess-stdout streaming is built
        (see Out of Scope in docs/superpowers/specs/2026-07-29-chat-copilot-design.md).
        """
        yield self.complete(prompt)
