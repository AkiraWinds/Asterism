from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_data_root
from app.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderMissingError,
    ProviderTimeoutError,
)
from app.providers.factory import build_provider
from app.repositories.config_repository import ConfigError, load_config
from app.schemas.agent import AgentCompleteRequest, AgentCompleteResponse, AgentErrorResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/complete", response_model=AgentCompleteResponse)
def complete_endpoint(payload: AgentCompleteRequest):
    data_root = get_data_root()

    try:
        config = load_config(data_root)
    except ConfigError as exc:
        return JSONResponse(
            status_code=400,
            content=AgentErrorResponse(error_type="config", message=str(exc)).model_dump(),
        )

    provider = build_provider(config, data_root)

    try:
        response_text = provider.complete(payload.prompt)
    except ProviderMissingError as exc:
        return JSONResponse(
            status_code=400,
            content=AgentErrorResponse(error_type="missing", message=str(exc)).model_dump(),
        )
    except ProviderConfigError as exc:
        return JSONResponse(
            status_code=400,
            content=AgentErrorResponse(error_type="config", message=str(exc)).model_dump(),
        )
    except ProviderTimeoutError as exc:
        return JSONResponse(
            status_code=504,
            content=AgentErrorResponse(error_type="timeout", message=str(exc)).model_dump(),
        )
    except ProviderError as exc:
        return JSONResponse(
            status_code=502,
            content=AgentErrorResponse(error_type="error", message=str(exc)).model_dump(),
        )

    return AgentCompleteResponse(response=response_text)
