
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEPENDENCY_SECTIONS = {
    "dependencies": "production",
    "devDependencies": "development",
    "optionalDependencies": "optional",
    "peerDependencies": "peer",
}


def parse_package_json(path: str | Path) -> list[dict[str, Any]]:
    """Extract dependency declarations from an npm package.json manifest."""
    manifest = Path(path)

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to parse {manifest}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {manifest}")

    results: list[dict[str, Any]] = []

    for section, dependency_type in DEPENDENCY_SECTIONS.items():
        dependencies = data.get(section, {})

        if not isinstance(dependencies, dict):
            continue

        for package_name, version in sorted(dependencies.items()):
            if not isinstance(package_name, str) or not package_name:
                continue
            if not isinstance(version, str) or not version:
                continue

            results.append({
                "name": package_name,
                "ecosystem": "npm",
                "declared_version": version,
                "resolved_version": None,
                "dependency_type": dependency_type,
                "direct": True,
                "evidence": {
                    "path": manifest.as_posix(),
                    "section": section,
                },
            })

    return results


def parse_package_lock(path: str | Path) -> list[dict[str, Any]]:
    """Extract resolved npm package versions from lockfile v1, v2, or v3."""
    lockfile = Path(path)

    try:
        data = json.loads(lockfile.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to parse {lockfile}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {lockfile}")

    lockfile_version = data.get("lockfileVersion")
    if lockfile_version not in (1, 2, 3):
        raise ValueError(
            f"Unsupported npm lockfile version: {lockfile_version!r}"
        )

    results: list[dict[str, Any]] = []

    def add_package(
        name: str,
        details: dict[str, Any],
        package_path: str,
    ) -> None:
        version = details.get("version")
        if not isinstance(version, str) or not version:
            return

        results.append({
            "name": name,
            "ecosystem": "npm",
            "declared_version": None,
            "resolved_version": version,
            "dependency_type": "lockfile",
            "direct": False,
            "evidence": {
                "path": lockfile.as_posix(),
                "package_path": package_path,
            },
        })

    if isinstance(data.get("packages"), dict):
        # npm lockfile v2/v3: packages are listed by installation path.
        for package_path, details in sorted(data["packages"].items()):
            if not isinstance(package_path, str):
                continue
            if not isinstance(details, dict):
                continue

            marker = "node_modules/"
            if marker not in package_path:
                continue

            name = package_path.rsplit(marker, 1)[-1]
            if not name:
                continue

            add_package(name, details, package_path)

    elif isinstance(data.get("dependencies"), dict):
        # npm lockfile v1: dependencies are represented as a nested tree.
        def walk_dependencies(
            dependencies: dict[str, Any],
            parent_path: str = "",
        ) -> None:
            for name, details in sorted(dependencies.items()):
                if not isinstance(name, str) or not isinstance(details, dict):
                    continue

                package_path = (
                    f"{parent_path}/node_modules/{name}"
                    if parent_path
                    else f"node_modules/{name}"
                )

                add_package(name, details, package_path)

                nested = details.get("dependencies")
                if isinstance(nested, dict):
                    walk_dependencies(nested, package_path)

        walk_dependencies(data["dependencies"])

    else:
        raise ValueError(
            "npm lockfile contains neither a packages nor dependencies object"
        )

    return results