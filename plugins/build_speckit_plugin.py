#!/usr/bin/env python3
"""Build the Devin plugin from Specify CLI's rendered Devin integration."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from packaging.version import Version
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
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
CORE_COMMAND_REFERENCE = re.compile(
    r"/speckit-(constitution|specify|clarify|plan|checklist|tasks|analyze|implement|converge)\b"
)
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
OPT_IN_NOTE = (
    "Only use in projects that have opted into Spec Kit (a .specify/ directory "
    "exists at the repo root) or when the user has invoked a /speckit: command "
    "in this session."
)
OPT_IN_GUARD = (
    "**Opt-in check:** If the user did not invoke this skill directly (by typing "
    "`/speckit:<name>`) and has not invoked any `/speckit:` command earlier in "
    "this session, first check whether `.specify/` exists at the project root. "
    "If it does not, this project has not opted into Spec Kit: stop following "
    "this skill and continue the task normally without Spec Kit."
)
INIT_DESCRIPTION = (
    "Opt this project into Spec Kit spec-driven development: installs .specify/ "
    "scripts and templates. After opting in, the other speckit skills activate "
    "automatically as needed."
)


BOOTSTRAP_SCRIPT = r'''#!/usr/bin/env bash

set -e

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if project_root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null); then
    :
else
    project_root=$PWD
fi

source_root="$script_dir/specify"
target_root="$project_root/.specify"
refreshed_scripts=0
refreshed_templates=0
created_configs=0
preserved_configs=0

mkdir -p "$target_root/scripts/bash" "$target_root/templates"

for source_file in "$source_root/scripts/bash"/*.sh; do
    [ -f "$source_file" ] || continue
    destination="$target_root/scripts/bash/$(basename "$source_file")"
    cp "$source_file" "$destination"
    chmod +x "$destination"
    refreshed_scripts=$((refreshed_scripts + 1))
done

for source_file in "$source_root/templates"/*.md; do
    [ -f "$source_file" ] || continue
    cp "$source_file" "$target_root/templates/"
    refreshed_templates=$((refreshed_templates + 1))
done

copy_if_missing() {
    source_file=$1
    destination=$2
    if [ -e "$destination" ]; then
        preserved_configs=$((preserved_configs + 1))
    else
        cp "$source_file" "$destination"
        created_configs=$((created_configs + 1))
    fi
}

mkdir -p "$target_root/memory"
copy_if_missing "$source_root/memory/constitution.md" "$target_root/memory/constitution.md"
copy_if_missing "$source_root/init-options.json" "$target_root/init-options.json"
copy_if_missing "$source_root/integration.json" "$target_root/integration.json"
copy_if_missing "$source_root/.gitignore" "$target_root/.gitignore"

printf 'Spec Kit bootstrap: %s\n' "$project_root"
printf 'Refreshed %s scripts and %s templates.\n' "$refreshed_scripts" "$refreshed_templates"
printf 'Created %s configuration files; preserved %s existing configuration files.\n' \
    "$created_configs" "$preserved_configs"
'''


BOOTSTRAP_INSTRUCTIONS = '''## Plugin Bootstrap

Before anything else, from the project root run:
`bash "<BASE_DIR>/../../assets/speckit-bootstrap.sh"`
where `<BASE_DIR>` is the "Base directory" shown for this skill. If no base directory was shown, locate the script with `find / -type f -path '*/assets/speckit-bootstrap.sh' 2>/dev/null | head -1`.
This idempotently installs Spec Kit's scripts and templates into `.specify/`. Then continue below.
'''

WORKFLOW_BOOTSTRAP_INSTRUCTIONS = BOOTSTRAP_INSTRUCTIONS.replace(
    "## Plugin Bootstrap\n\n",
    "## Plugin Bootstrap\n\n" + OPT_IN_GUARD + "\n\n",
    1,
)


def _rendered_skill(source: Path, command: str) -> str:
    if not source.is_file():
        raise RuntimeError(f"Expected rendered skill is missing: {source}")
    text = source.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if not match:
        raise RuntimeError(f"Rendered skill has no YAML frontmatter: {source}")

    lines = []
    found_name = False
    found_description = False
    found_metadata = False
    for line in match.group(1).splitlines():
        if line.startswith("name:"):
            lines.append(f"name: {command}")
            found_name = True
        elif line.startswith("compatibility:"):
            continue
        elif line.startswith("description:"):
            try:
                description = yaml.safe_load(line)["description"]
            except (KeyError, TypeError, yaml.YAMLError) as exc:
                raise RuntimeError(
                    f"Rendered skill has an invalid description: {source}"
                ) from exc
            if not isinstance(description, str):
                raise RuntimeError(
                    f"Rendered skill has a non-string description: {source}"
                )
            lines.append(
                "description: "
                + json.dumps(f"{description} {OPT_IN_NOTE}")
            )
            found_description = True
        else:
            lines.append(line)
            found_metadata |= line.startswith("metadata:")
    if not found_name or not found_description or not found_metadata:
        raise RuntimeError(
            f"Rendered skill is missing expected name, description, or metadata: {source}"
        )

    body = text[match.end() :]
    if "## User Input" not in body:
        raise RuntimeError(
            f"Rendered skill is missing the expected User Input section: {source}"
        )
    rewritten_body = CORE_COMMAND_REFERENCE.sub(r"/speckit:\1", body)
    if CORE_COMMAND_REFERENCE.search(rewritten_body):
        raise RuntimeError(
            f"Core command reference was not rewritten in rendered skill: {source}"
        )

    return (
        "---\n"
        + "\n".join(lines)
        + "\n---\n\n"
        + WORKFLOW_BOOTSTRAP_INSTRUCTIONS
        + "\n"
        + rewritten_body
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _rewrite_core_command_refs(text: str) -> str:
    return CORE_COMMAND_REFERENCE.sub(r"/speckit:\1", text)


def _plugin_version(version: str) -> str:
    parsed = Version(version)
    release = ".".join(str(part) for part in parsed.release)
    prerelease = []
    if parsed.pre:
        prerelease.extend(
            ({"a": "alpha", "b": "beta", "rc": "rc"}[parsed.pre[0]], str(parsed.pre[1]))
        )
    if parsed.post is not None:
        prerelease.extend(("post", str(parsed.post)))
    if parsed.dev is not None:
        prerelease.extend(("dev", str(parsed.dev)))
    semver = release + ("-" + ".".join(prerelease) if prerelease else "")
    if parsed.local:
        semver += "+" + re.sub(r"[^0-9A-Za-z.-]", "-", parsed.local)
    return semver


def build(output: Path) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for generated in (output / ".devin-plugin", output / "skills", output / "assets"):
        if generated.is_dir():
            shutil.rmtree(generated)
        elif generated.exists():
            generated.unlink()

    with tempfile.TemporaryDirectory(prefix="speckit-devin-plugin-") as temporary:
        temporary_root = Path(temporary)
        command = [
            sys.executable,
            "-c",
            "from specify_cli import main; main()",
            "init",
            "--here",
            "--integration",
            "devin",
            "--script",
            "sh",
            "--ignore-agent-tools",
            "--force",
        ]
        rendered = subprocess.run(
            command,
            cwd=temporary_root,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    part
                    for part in (
                        str(REPO_ROOT / "src"),
                        os.environ.get("PYTHONPATH", ""),
                    )
                    if part
                ),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        if rendered.returncode:
            raise RuntimeError(
                "Specify init failed:\n" + rendered.stdout + rendered.stderr
            )

        rendered_skills = temporary_root / ".devin" / "skills"
        for name in COMMANDS:
            source = rendered_skills / f"speckit-{name}" / "SKILL.md"
            destination = output / "skills" / name / "SKILL.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(_rendered_skill(source, name), encoding="utf-8")

        assets_source = temporary_root / ".specify"
        assets_destination = output / "assets" / "specify"
        for relative in (
            Path("scripts/bash"),
            Path("templates"),
            Path("memory/constitution.md"),
            Path(".gitignore"),
            Path("init-options.json"),
            Path("integration.json"),
        ):
            source = assets_source / relative
            if not source.exists():
                raise RuntimeError(f"Expected rendered asset is missing: {source}")
            destination = assets_destination / relative
            if source.is_dir():
                for asset in sorted(source.iterdir()):
                    if asset.is_file():
                        destination.mkdir(parents=True, exist_ok=True)
                        copied_asset = destination / asset.name
                        shutil.copy2(asset, copied_asset)
                        if relative in (Path("scripts/bash"), Path("templates")):
                            copied_asset.write_text(
                                _rewrite_core_command_refs(
                                    copied_asset.read_text(encoding="utf-8")
                                ),
                                encoding="utf-8",
                            )
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

        integration_path = assets_destination / "integration.json"
        integration = json.loads(integration_path.read_text(encoding="utf-8"))
        settings = integration.get("integration_settings")
        if not isinstance(settings, dict) or not isinstance(settings.get("devin"), dict):
            raise RuntimeError("Rendered integration.json has no Devin settings")
        settings["devin"]["invoke_separator"] = ":"
        _write_json(integration_path, integration)

    bootstrap_path = output / "assets" / "speckit-bootstrap.sh"
    bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_path.write_text(BOOTSTRAP_SCRIPT, encoding="utf-8")
    bootstrap_path.chmod(0o755)

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    manifest = {
        "name": "speckit",
        "version": _plugin_version(version),
        "description": (
            "Spec-Driven Development with GitHub Spec Kit: constitution, specify, "
            "clarify, plan, tasks, analyze, implement"
        ),
        "repository": "https://github.com/aaron-cog-gtm-gh-org/spec-kit",
        "license": "MIT",
        "keywords": [
            "spec-driven-development",
            "specification",
            "planning",
            "github-spec-kit",
        ],
    }
    _write_json(output / ".devin-plugin" / "plugin.json", manifest)

    init_body = (
        BOOTSTRAP_INSTRUCTIONS
        + "\nAfter bootstrap, report what was installed. Use this workflow:\n\n"
        + "1. `/speckit:constitution`\n"
        + "2. `/speckit:specify`\n"
        + "3. Optionally, `/speckit:clarify`\n"
        + "4. `/speckit:plan`\n"
        + "5. Optionally, `/speckit:checklist`\n"
        + "6. `/speckit:tasks`\n"
        + "7. Optionally, `/speckit:analyze`\n"
        + "8. `/speckit:implement`\n"
        + "9. Optionally, `/speckit:converge`\n"
    )
    init_skill = (
        "---\n"
        "name: init\n"
        f"description: {json.dumps(INIT_DESCRIPTION)}\n"
        "triggers:\n"
        "  - user\n"
        "---\n\n"
        + init_body
    )
    init_skill_path = output / "skills" / "init" / "SKILL.md"
    init_skill_path.parent.mkdir(parents=True, exist_ok=True)
    init_skill_path.write_text(init_skill, encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "plugins" / "speckit",
        help="Output directory (default: plugins/speckit)",
    )
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Spec Kit plugin build failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
