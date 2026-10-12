# GitHub Spec Kit for Devin

This plugin brings GitHub Spec Kit's spec-driven development skills to Devin:
create a constitution, specify and plan a feature, generate tasks, and implement
the resulting plan. It bundles the scripts and templates used by the Specify
CLI, so you can use the workflow without running `specify init`.

## Install

**CLI**

```sh
devin plugins install aaron-cog-gtm-gh-org/spec-kit#plugins/speckit
```

**Customize**

Open **Customize → Plugins → From repository**, enter
`aaron-cog-gtm-gh-org/spec-kit`, and set the subdirectory to `plugins/speckit`.

## Workflow

| Skill | Purpose |
| --- | --- |
| `/speckit:init` | Install or refresh Spec Kit scripts and templates |
| `/speckit:constitution` | Create or update project principles |
| `/speckit:specify` | Create or update a feature specification |
| `/speckit:clarify` | Resolve ambiguities in a specification (optional) |
| `/speckit:plan` | Create implementation design artifacts |
| `/speckit:checklist` | Generate a requirements-quality checklist (optional) |
| `/speckit:tasks` | Generate dependency-ordered implementation tasks |
| `/speckit:analyze` | Check the specification, plan, and tasks for consistency (optional) |
| `/speckit:implement` | Execute the implementation tasks |
| `/speckit:converge` | Assess implementation and append remaining work (optional) |

The usual flow is constitution → specify → clarify (optional) → plan →
checklist (optional) → tasks → analyze (optional) → implement → converge
(optional).

## Bootstrap

Each workflow skill first runs the bundled bootstrap script. It installs or
refreshes `.specify/scripts/bash/*.sh` and `.specify/templates/*.md` in the
project, and creates the initial constitution and configuration files only
when they are missing. Existing constitution and configuration files are
preserved. Use `/speckit:init` to bootstrap explicitly or report what was
installed.

To regenerate the bundled skills and assets after pulling upstream changes,
run from the Spec Kit repository:

```sh
uv run --python 3.11 python plugins/build_speckit_plugin.py
```
