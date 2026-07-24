from pathlib import Path

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


def test_production_compose_uses_published_image_without_local_build() -> None:
    compose = (PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8")

    assert "image: ${COMRADBOT_IMAGE:-dheovani/comradbot:1.0.0}" in compose
    assert "\n    build:" not in compose
    assert "comradbot-data:/app/data" in compose
    assert "restart: unless-stopped" in compose
