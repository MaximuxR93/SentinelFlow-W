import subprocess

from fastapi import APIRouter, HTTPException

from app.schemas.repository import (
    RepositoryAnalyzeRequest,
    RepositoryMetadata,
)
from app.services.repository_service import repository_service


router = APIRouter(
    prefix="/api/repositories",
    tags=["Repositories"],
)


@router.post(
    "/analyze",
    response_model=RepositoryMetadata,
)
def analyze_repository(
    request: RepositoryAnalyzeRequest,
):
    try:
        return repository_service.analyze(
            str(request.url)
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="Repository clone timed out.",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )