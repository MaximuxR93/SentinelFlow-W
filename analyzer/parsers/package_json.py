
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


def parse_package_json(path: str | Path) -> list[dict[str, Any]]:
    """Extract declared npm dependencies with source evidence."""
    manifest = Path(path)

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to parse {manifest}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {manifest}")

    results = []
    for section in DEPENDENCY_SECTIONS:
        dependencies = data.get(section, {})
        if not isinstance(dependencies, dict):
            continue

        for name, specifier in sorted(dependencies.items()):
            if not isinstance(name, str) or not isinstance(specifier, str):
                continue

            results.append({
                "name": name,
                "ecosystem": "npm",
                "declared_version": specifier,
                "resolved_version": None,
                "dependency_type": section,
                "direct": True,
                "evidence": {
                    "path": manifest.as_posix(),
                    "section": section,
                },
            })

    return results


def parse_package_lock(path: str | Path) -> list[dict[str, Any]]:
    """Extract installed package versions from npm lockfile v2/v3."""
    lockfile = Path(path)

    try:
        data = json.loads(lockfile.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to parse {lockfile}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {lockfile}")

    packages = data.get("packages", {})
    if not isinstance(packages, dict):
        return []

    results = []
    for package_path, details in sorted(packages.items()):
        if not package_path or not isinstance(details, dict):
            continue

        # npm lockfiles use node_modules paths, including nested packages.
        marker = "node_modules/"
        if marker not in package_path:
            continue

        name = package_path.rsplit(marker, 1)[-1]
        version = details.get("version")
        if not isinstance(version, str):
            continue

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

    return results