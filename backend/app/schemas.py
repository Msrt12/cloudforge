from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class EnvironmentResponse(BaseModel):
    id: int
    name: str
    previous_version: Optional[str] = None
    current_version: Optional[str] = None
    status: str
    min_replicas: int
    max_replicas: int
    target_cpu: int
    model_config = ConfigDict(from_attributes=True)


class ApplicationCreate(BaseModel):
    name: str
    repository: str


class ApplicationResponse(BaseModel):
    id: int
    name: str
    repository: str
    environments: List[EnvironmentResponse]

    model_config = ConfigDict(from_attributes=True)

class DeployRequest(BaseModel):
    environment: str
    version: str

class PromoteRequest(BaseModel):
    target_environment: str


class RollbackRequest(BaseModel):
    environment: str


class ScalingRequest(BaseModel):
    environment: str
    min_replicas: int
    max_replicas: int
    target_cpu: int