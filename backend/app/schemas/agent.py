from pydantic import BaseModel


class AgentCompleteRequest(BaseModel):
    prompt: str


class AgentCompleteResponse(BaseModel):
    response: str


class AgentErrorResponse(BaseModel):
    error_type: str
    message: str
