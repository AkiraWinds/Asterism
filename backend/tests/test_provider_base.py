import pytest

from app.providers.base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    ProviderMissingError,
    ProviderTimeoutError,
)


def test_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Provider()


def test_provider_error_subtypes_carry_message():
    for error_cls in (ProviderError, ProviderMissingError, ProviderConfigError, ProviderTimeoutError):
        error = error_cls("something went wrong")
        assert error.message == "something went wrong"
        assert str(error) == "something went wrong"


@pytest.mark.parametrize(
    "error_cls",
    [ProviderMissingError, ProviderConfigError, ProviderTimeoutError],
)
def test_provider_error_subtypes_are_provider_errors(error_cls):
    assert issubclass(error_cls, ProviderError)
