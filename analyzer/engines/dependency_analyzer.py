
from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from parsers.package_json import parse_package_json, parse_package_lock
from parsers.python_project import parse_requirements, parse_pyproject


IGNORED_DIRS = {
    ".git",
    ".next",
    "node_modules",
    "dist",
    "build",
    "out",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".cache",
}


class DependencyAnalyzer:
    """Collect dependency declarations and lockfile versions without executing code."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

        if not self.root.is_dir():
            raise NotADirectoryError(f"Invalid repository: {self.root}")

    def _iter_files(self):
        """Yield repository files while pruning ignored directories."""
        for current_dir, dirs, filenames in os.walk(self.root):
            # Prune ignored directories before os.walk descends into them.
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in IGNORED_DIRS
            ]

            for filename in filenames:
                yield Path(current_dir) / filename

    def _relative(self, path: Path) -> str:
        """Return a repository-relative path with POSIX separators."""
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            # Avoid exposing external absolute paths in analyzer output.
            return path.name

    def _normalize_evidence_paths(
        self,
        items: list[dict[str, Any]],
    ) -> None:
        """Normalize evidence paths to repository-relative paths."""
        for item in items:
            evidence = item.get("evidence")

            if not isinstance(evidence, dict):
                continue

            evidence_path = evidence.get("path")

            if evidence_path:
                evidence["path"] = self._relative(Path(evidence_path))

    def analyze(self) -> dict[str, Any]:
        """Analyze supported dependency manifests and lockfiles."""
        files = list(self._iter_files())

        declarations: list[dict[str, Any]] = []
        locked: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for path in files:
            name = path.name.lower()

            try:
                if name == "package.json":
                    declarations.extend(parse_package_json(path))

                elif name == "package-lock.json":
                    locked.extend(parse_package_lock(path))

                elif name in {"requirements.txt", "requirements-dev.txt"}:
                    declarations.extend(parse_requirements(path))

                elif name == "pyproject.toml":
                    declarations.extend(parse_pyproject(path))

            except (ValueError, OSError) as exc:
                errors.append(
                    {
                        "path": self._relative(path),
                        "error": str(exc),
                    }
                )

        # Ensure all evidence paths are repository-relative.
        self._normalize_evidence_paths(declarations)
        self._normalize_evidence_paths(locked)

        # Index resolved lockfile versions by ecosystem and package name.
        lock_index: dict[tuple[str, str], list[str]] = defaultdict(list)

        for item in locked:
            key = (
                item["ecosystem"],
                item["name"].lower(),
            )
            version = item.get("resolved_version")

            if version and version not in lock_index[key]:
                lock_index[key].append(version)

        # Enrich declarations when exactly one matching lockfile version exists.
        for item in declarations:
            key = (
                item["ecosystem"],
                item["name"].lower(),
            )
            versions = lock_index.get(key, [])

            if len(versions) == 1:
                item["resolved_version"] = versions[0]

            elif len(versions) > 1:
                item["lockfile_versions"] = sorted(versions)

        # Deduplicate identical declarations while preserving source evidence.
        unique: dict[tuple[Any, ...], dict[str, Any]] = {}

        for item in declarations:
            evidence = item.get("evidence", {})

            key = (
                item["ecosystem"],
                item["name"],
                item["declared_version"],
                item["dependency_type"],
                evidence.get("path"),
                evidence.get("line"),
            )

            unique[key] = item

        dependencies = sorted(
            unique.values(),
            key=lambda item: (
                item["ecosystem"],
                item["name"],
                item.get("evidence", {}).get("path", ""),
            ),
        )

        # Count dependencies by ecosystem.
        ecosystem_counts: dict[str, int] = defaultdict(int)

        for item in dependencies:
            ecosystem_counts[item["ecosystem"]] += 1

        return {
            "repository": self.root.name,
            "summary": {
                "total_declared": len(dependencies),
                "npm": ecosystem_counts["npm"],
                "pypi": ecosystem_counts["pypi"],
                "lockfile_packages": len(locked),
                "parse_errors": len(errors),
            },
            "dependencies": dependencies,
            "lockfile_packages": locked,
            "errors": errors,
            "metadata": {
    "analysis_type": "manifest-and-lockfile",
    "executed_repository_code": False,
    "vulnerability_matching": (
        "OSV exact-version matching is performed by VulnerabilityScanner"
    ),
},
        }