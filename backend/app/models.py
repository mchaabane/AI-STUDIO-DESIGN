from datetime import datetime, timezone

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Project(BaseModel):
    id: str
    name: str
    type: str = "web"
    status: str = "generated"

    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    current_version: int = 1


class ProjectVersion(BaseModel):
    version: int
    prompt: str
    html: str

    generation_time_ms: int | None = None

    created_at: str = Field(default_factory=now_iso)


class ProjectDetail(Project):
    versions: list[ProjectVersion] = []


class PromptRequest(BaseModel):
    prompt: str
    title: str | None = None
    project_id: str | None = None


class Intent(BaseModel):
    action: str
    project_id: str | None = None
    project_name: str | None = None
