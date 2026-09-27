
from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any


_REQUIREMENT_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*"
    r"(\[[^\]]+\])?\s*(.*)$"
)


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _make_dependency(
    name: str,
    specifier: str,
    source: Path,
    dependency_type: str,
) -> dict[str, Any]:
    return {
        "name": _normalize_name(name),
        "ecosystem": "pypi",
        "declared_version": specifier.strip(),
        "resolved_version": None,
        "dependency_type": dependency_type,
        "direct": True,
        "evidence": {
            "path": source.as_posix(),
        },
    }


def parse_requirements(path: str | Path) -> list[dict[str, Any]]:
    """Parse common pip requirements lines; skip options and references."""
    source = Path(path)
    results = []

    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"Unable to read {source}: {exc}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http:", "https:")):
            continue

        match = _REQUIREMENT_RE.match(line)
        if not match:
            continue

        name, extras, specifier = match.groups()
        if "@" in name or name.startswith("."):
            continue

        results.append({
            **_make_dependency(name, specifier, source, "requirements"),
            "extras": extras[1:-1].split(",") if extras else [],
            "evidence": {
                "path": source.as_posix(),
                "line": line_number,
            },
        })

    return results


def parse_pyproject(path: str | Path) -> list[dict[str, Any]]:
    """Parse PEP 621 project dependencies and common Poetry groups."""
    source = Path(path)

    try:
        with source.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Unable to parse {source}: {exc}") from exc

    results = []
    project = data.get("project", {})
    if isinstance(project, dict):
        for requirement in project.get("dependencies", []):
            if not isinstance(requirement, str):
                continue
            match = _REQUIREMENT_RE.match(requirement)
            if match:
                name, _, specifier = match.groups()
                results.append(
                    _make_dependency(name, specifier, source, "project")
                )

        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group, requirements in optional.items():
                if not isinstance(requirements, list):
                    continue
                for requirement in requirements:
                    if not isinstance(requirement, str):
                        continue
                    match = _REQUIREMENT_RE.match(requirement)
                    if match:
                        name, _, specifier = match.groups()
                        results.append(
                            _make_dependency(
                                name, specifier, source, f"optional:{group}"
                            )
                        )

    # Poetry's dependency tables are commonly used in pyproject.toml.
    poetry = data.get("tool", {}).get("poetry", {})
    if isinstance(poetry, dict):
        for group_name, section in (
            ("poetry", poetry.get("dependencies", {})),
            ("poetry-dev", poetry.get("dev-dependencies", {})),
        ):
            if not isinstance(section, dict):
                continue
            for name, value in section.items():
                if name.lower() == "python":
                    continue
                if isinstance(value, str):
                    specifier = value
                elif isinstance(value, dict):
                    specifier = str(value.get("version", ""))
                else:
                    continue
                results.append(
                    _make_dependency(name, specifier, source, group_name)
                )

    return results