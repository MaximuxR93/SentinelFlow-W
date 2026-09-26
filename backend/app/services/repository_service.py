import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.schemas.repository import RepositoryMetadata


class RepositoryService:

    def __init__(self):
        self.workspace = Path(settings.workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _repository_name(self, url: str) -> str:
        path = urlparse(url).path.strip("/")
        name = path.split("/")[-1]

        if name.endswith(".git"):
            name = name[:-4]

        return name

    def _clone_repository(self, url: str, destination: Path):
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                url,
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to clone repository: {result.stderr.strip()}"
            )

    def _count_files(self, repository_path: Path) -> int:
        ignored_directories = {
            ".git",
            "node_modules",
            ".next",
            "dist",
            "build",
            ".venv",
            "venv",
            "__pycache__",
        }

        count = 0

        for path in repository_path.rglob("*"):
            if not path.is_file():
                continue

            if any(part in ignored_directories for part in path.parts):
                continue

            count += 1

        return count

    def _detect_languages(self, repository_path: Path) -> list[str]:
        extensions = {
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".py": "Python",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".cs": "C#",
            ".php": "PHP",
            ".rb": "Ruby",
        }

        detected = set()

        for path in repository_path.rglob("*"):
            if not path.is_file():
                continue

            if any(
                part in {
                    ".git",
                    "node_modules",
                    ".next",
                    "dist",
                    "build",
                    ".venv",
                    "venv",
                }
                for part in path.parts
            ):
                continue

            language = extensions.get(path.suffix.lower())

            if language:
                detected.add(language)

        return sorted(detected)

    def _read_package_json(self, repository_path: Path):
        package_file = repository_path / "package.json"

        if not package_file.exists():
            return {}

        try:
            return json.loads(
                package_file.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _detect_framework(self, repository_path: Path) -> str | None:
        package = self._read_package_json(repository_path)

        dependencies = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }

        if "next" in dependencies:
            return "Next.js"

        if "react" in dependencies:
            return "React"

        if "express" in dependencies:
            return "Express"

        if (repository_path / "manage.py").exists():
            return "Django"

        if any(
            repository_path.glob("requirements*.txt")
        ):
            return "Python"

        if (repository_path / "pom.xml").exists():
            return "Spring"

        return None

    def _detect_package_manager(
        self,
        repository_path: Path,
    ) -> str | None:

        if (repository_path / "pnpm-lock.yaml").exists():
            return "pnpm"

        if (repository_path / "yarn.lock").exists():
            return "yarn"

        if (repository_path / "package-lock.json").exists():
            return "npm"

        if (repository_path / "bun.lockb").exists():
            return "bun"

        if (repository_path / "bun.lock").exists():
            return "bun"

        if (
            (repository_path / "requirements.txt").exists()
            or (repository_path / "pyproject.toml").exists()
        ):
            return "pip"

        if (repository_path / "pom.xml").exists():
            return "maven"

        return None

    def _detect_database(
        self,
        repository_path: Path,
    ) -> str | None:

        package = self._read_package_json(repository_path)

        dependencies = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }

        database_signatures = {
            "mongoose": "MongoDB",
            "mongodb": "MongoDB",
            "pg": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mysql": "MySQL",
            "mysql2": "MySQL",
            "redis": "Redis",
            "prisma": "Prisma",
            "drizzle-orm": "Drizzle",
        }

        for dependency, database in database_signatures.items():
            if dependency in dependencies:
                return database

        return None

    def _count_api_routes(
        self,
        repository_path: Path,
    ) -> int:

        route_patterns = [
            "route.ts",
            "route.js",
            "route.tsx",
            "route.jsx",
        ]

        count = 0

        for pattern in route_patterns:
            count += len(
                list(repository_path.rglob(pattern))
            )

        return count

    def _detect_infrastructure(
        self,
        repository_path: Path,
    ) -> tuple[bool, bool]:

        docker = any(
            repository_path.glob("Dockerfile*")
        )

        github_actions = (
            repository_path / ".github" / "workflows"
        ).exists()

        return docker, github_actions

    def analyze(self, url: str) -> RepositoryMetadata:

        repository_name = self._repository_name(url)

        destination = (
            self.workspace / repository_name
        )

        if destination.exists():
            shutil.rmtree(destination)

        self._clone_repository(
            url,
            destination,
        )

        files = self._count_files(destination)

        languages = self._detect_languages(
            destination
        )

        framework = self._detect_framework(
            destination
        )

        package_manager = self._detect_package_manager(
            destination
        )

        database = self._detect_database(
            destination
        )

        api_routes = self._count_api_routes(
            destination
        )

        docker, github_actions = (
            self._detect_infrastructure(
                destination
            )
        )

        return RepositoryMetadata(
            name=repository_name,
            url=url,
            framework=framework,
            languages=languages,
            package_manager=package_manager,
            database=database,
            files=files,
            api_routes=api_routes,
            docker=docker,
            github_actions=github_actions,
        )


repository_service = RepositoryService()