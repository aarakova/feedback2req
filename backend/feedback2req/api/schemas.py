from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class LoginCredentials(ClosedModel):
    login: str = Field(min_length=1, max_length=256)
    password: SecretStr = Field(min_length=1, max_length=1024)


class Credentials(LoginCredentials):
    password: SecretStr = Field(min_length=12, max_length=1024)


class ProjectName(ClosedModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class AccessChange(ClosedModel):
    can_approve: Annotated[bool, Field(strict=True)]


class UserView(ClosedModel):
    id: UUID
    login: str


def user_view(user):
    return {"id": str(user.id), "login": user.login}


def project_view(project, rights):
    return {
        "id": str(project.id),
        "owner_id": str(project.owner_id),
        "name": project.name,
        "execution_mode": project.execution_mode,
        "permissions": rights,
    }
