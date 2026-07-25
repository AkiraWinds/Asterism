from abc import ABC, abstractmethod


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
