from pydantic import BaseModel, HttpUrl, Field


class RepositoryAnalyzeRequest(BaseModel):
    url: HttpUrl


class RepositoryMetadata(BaseModel):
    name: str
    url: str
    framework: str | None = None
    languages: list[str] = Field(default_factory=list)
    package_manager: str | None = None
    database: str | None = None
    files: int = 0
    api_routes: int = 0
    docker: bool = False
    github_actions: bool = False