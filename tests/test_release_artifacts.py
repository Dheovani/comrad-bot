from pathlib import Path

import pytest

from comradbot import __version__
from scripts.validate_release import normalized_release_version, validate_release

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_container_release_workflow_publishes_versioned_multi_platform_image() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/publish-container.yml").read_text(
        encoding="utf-8"
    )

    assert "types:\n      - published" in workflow
    assert "username: ${{ vars.DOCKER_USERNAME }}" in workflow
    assert "password: ${{ secrets.DOCKER_TOKEN }}" in workflow
    assert "type=semver,pattern={{version}},value=" in workflow
    assert "type=semver,pattern={{major}}.{{minor}},value=" in workflow
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "push: true" in workflow
    assert "provenance: mode=max" in workflow
    assert "sbom: true" in workflow
    assert "python scripts/validate_release.py" in workflow
    assert "gh release upload" in workflow
    assert ".env.example compose.production.yaml" in workflow


def test_production_compose_uses_published_image_without_local_build() -> None:
    compose = (PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8")

    assert "image: ${COMRADBOT_IMAGE:-theovani/comradbot:1.1.0}" in compose
    assert "\n    build:" not in compose
    assert "comradbot-data:/app/data" in compose
    assert "restart: unless-stopped" in compose


@pytest.mark.parametrize("tag", ["v1.1.0", "1.1.0"])
def test_release_validator_accepts_matching_semantic_version(tag: str) -> None:
    assert normalized_release_version(tag) == "1.1.0"
    assert validate_release(tag, PROJECT_ROOT) == "1.1.0"
    assert __version__ == "1.1.0"


@pytest.mark.parametrize("tag", ["v1", "1.0", "latest", "v1.0.0-beta"])
def test_release_validator_rejects_non_release_tags(tag: str) -> None:
    with pytest.raises(ValueError, match="Release tag must use"):
        normalized_release_version(tag)


def test_release_validator_rejects_version_mismatch(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.0.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [1.0.0]\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"does not match pyproject\.toml"):
        validate_release("v1.0.0", tmp_path)


def test_release_validator_requires_changelog_section(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no release section"):
        validate_release("v1.0.0", tmp_path)


def test_dependency_and_container_security_automation_is_configured() -> None:
    dependabot = (PROJECT_ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    security_workflow = (PROJECT_ROOT / ".github/workflows/container-security.yml").read_text(
        encoding="utf-8"
    )

    assert "package-ecosystem: pip" in dependabot
    assert "package-ecosystem: docker" in dependabot
    assert "package-ecosystem: github-actions" in dependabot
    assert "aquasecurity/trivy-action@v0.36.0" in security_workflow
    assert "github/codeql-action/upload-sarif@v4" in security_workflow
    assert "severity: HIGH,CRITICAL" in security_workflow
    assert 'exit-code: "1"' in security_workflow
