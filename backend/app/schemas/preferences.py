from pydantic import BaseModel


class PreferencesResponse(BaseModel):
    font_scale: float


class PreferencesUpdateRequest(BaseModel):
    font_scale: float
