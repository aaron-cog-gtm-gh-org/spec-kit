"""Tests for the generated Devin plugin."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from plugins.build_speckit_plugin import INIT_DESCRIPTION, OPT_IN_GUARD, OPT_IN_NOTE


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "speckit"
GENERATOR = PROJECT_ROOT / "plugins" / "build_speckit_plugin.py"
CORE_COMMANDS = (
    "constitution",
    "specify",
    "clarify",
    "plan",
    "checklist",
    "tasks",
    "analyze",
    "implement",
    "converge",
)
CORE_REFERENCE = re.compile(
    r"/speckit-(constitution|specify|clarify|plan|checklist|tasks|analyze|implement|converge)\b"
)


def _generated_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path.name != "README.md"
    }


def test_generated_plugin_is_in_sync(tmp_path: Path) -> None:
    generated = tmp_path / "speckit"
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(generated)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert _generated_files(generated) == _generated_files(PLUGIN_ROOT)
    for relative in sorted(_generated_files(PLUGIN_ROOT)):
        assert (generated / relative).read_bytes() == (PLUGIN_ROOT / relative).read_bytes()


def test_plugin_skills_have_expected_structure() -> None:
    skills = sorted(path for path in (PLUGIN_ROOT / "skills").iterdir() if path.is_dir())
    assert {path.name for path in skills} == {*CORE_COMMANDS, "init"}
    for skill_dir in skills:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        assert frontmatter is not None
        fields = frontmatter.group(1)
        assert re.search(rf'^name: "?{re.escape(skill_dir.name)}"?$', fields, re.MULTILINE)
        assert re.search(r"^description:\s*\S", fields, re.MULTILINE)
        metadata = yaml.safe_load(fields)
        body = text[frontmatter.end() :]
        if skill_dir.name == "init":
            assert metadata["triggers"] == ["user"]
            assert metadata["description"] == INIT_DESCRIPTION
            assert OPT_IN_GUARD not in body
        else:
            assert "triggers" not in metadata
            assert metadata["description"].endswith(OPT_IN_NOTE)
            assert (
                f"## Plugin Bootstrap\n\n{OPT_IN_GUARD}\n\nBefore anything else"
                in body
            )
        assert "## Plugin Bootstrap" in text
        assert not CORE_REFERENCE.search(text)
        assert "taskstoissues" not in text.lower()

    converge = (PLUGIN_ROOT / "skills" / "converge" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "replace dots (`.`) with hyphens (`-`)" in converge
    assert "`/speckit-git-commit`" in converge
    assert "/skill:speckit-" in converge


@pytest.mark.skipif(os.name == "nt", reason="Bash bootstrap tests are not supported on Windows")
def test_bootstrap_installs_refreshes_and_preserves_project_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subdirectory = project / "src" / "nested"
    subdirectory.mkdir(parents=True)

    bootstrap = PLUGIN_ROOT / "assets" / "speckit-bootstrap.sh"
    first = subprocess.run(
        ["bash", str(bootstrap)],
        cwd=subdirectory,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr + first.stdout
    assert f"Spec Kit bootstrap: {project}" in first.stdout

    scripts = sorted((project / ".specify" / "scripts" / "bash").glob("*.sh"))
    templates = sorted((project / ".specify" / "templates").glob("*.md"))
    assert scripts
    assert all(os.access(script, os.X_OK) for script in scripts)
    assert templates
    integration = json.loads(
        (project / ".specify" / "integration.json").read_text(encoding="utf-8")
    )
    assert integration["integration_settings"]["devin"]["invoke_separator"] == ":"

    constitution = project / ".specify" / "memory" / "constitution.md"
    constitution.write_text("Preserve this constitution.\n", encoding="utf-8")
    second = subprocess.run(
        ["bash", str(bootstrap)],
        cwd=subdirectory,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr + second.stdout
    assert constitution.read_text(encoding="utf-8") == "Preserve this constitution.\n"
    assert "Refreshed" in second.stdout
    assert "preserved 4 existing configuration files" in second.stdout

    create_feature = subprocess.run(
        [
            "bash",
            str(project / ".specify" / "scripts" / "bash" / "create-new-feature.sh"),
            "--json",
            "Add user auth",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert create_feature.returncode == 0, create_feature.stderr + create_feature.stdout

    prerequisites = subprocess.run(
        [
            "bash",
            str(project / ".specify" / "scripts" / "bash" / "check-prerequisites.sh"),
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert prerequisites.returncode != 0
    assert "/speckit:plan" in prerequisites.stderr + prerequisites.stdout
