"""UI-only preferences (currently just font_scale), stored in config.json
alongside provider config but read/written through their own loosely
validated load/save functions — see config_repository.load_font_scale /
save_font_scale. Kept separate from app/routers/agent.py because these
preferences have nothing to do with the provider abstraction.
"""

from fastapi import APIRouter, HTTPException

from app.core.config import get_data_root
from app.repositories.config_repository import ConfigError, load_font_scale, save_font_scale
from app.schemas.preferences import PreferencesResponse, PreferencesUpdateRequest

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesResponse)
def get_preferences() -> PreferencesResponse:
    data_root = get_data_root()
    return PreferencesResponse(font_scale=load_font_scale(data_root))


@router.put("", response_model=PreferencesResponse)
def update_preferences(payload: PreferencesUpdateRequest) -> PreferencesResponse:
    data_root = get_data_root()
    try:
        save_font_scale(data_root, payload.font_scale)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PreferencesResponse(font_scale=payload.font_scale)
