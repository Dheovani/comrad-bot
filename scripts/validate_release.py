from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_VERSION = re.compile(r"^(?:v)?(?P<version>\d+\.\d+\.\d+)$")


def normalized_release_version(tag: str) -> str:
    match = SEMANTIC_VERSION.fullmatch(tag.strip())
    if match is None:
        raise ValueError(f"Release tag must use vMAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH: {tag!r}")
    return match.group("version")


def validate_release(tag: str, project_root: Path = PROJECT_ROOT) -> str:
    version = normalized_release_version(tag)
    with (project_root / "pyproject.toml").open("rb") as pyproject_file:
        project_version = tomllib.load(pyproject_file)["project"]["version"]

    if project_version != version:
        raise ValueError(
            f"Release tag version {version} does not match pyproject.toml version {project_version}"
        )

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    if re.search(rf"^## \[{re.escape(version)}\](?:\s|$)", changelog, re.MULTILINE) is None:
        raise ValueError(f"CHANGELOG.md has no release section for {version}")

    return version


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate ComradBot release metadata")
    parser.add_argument("tag", help="Git tag to validate, such as v1.1.1")
    args = parser.parse_args()

    try:
        version = validate_release(args.tag)
    except ValueError as error:
        parser.error(str(error))
    print(version)


if __name__ == "__main__":
    main()
