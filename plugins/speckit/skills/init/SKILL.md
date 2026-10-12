---
name: init
description: "Opt this project into Spec Kit spec-driven development: installs .specify/ scripts and templates. After opting in, the other speckit skills activate automatically as needed."
triggers:
  - user
---

## Plugin Bootstrap

Before anything else, from the project root run:
`bash "<BASE_DIR>/../../assets/speckit-bootstrap.sh"`
where `<BASE_DIR>` is the "Base directory" shown for this skill. If no base directory was shown, locate the script with `find / -type f -path '*/assets/speckit-bootstrap.sh' 2>/dev/null | head -1`.
This idempotently installs Spec Kit's scripts and templates into `.specify/`. Then continue below.

After bootstrap, report what was installed. Use this workflow:

1. `/speckit:constitution`
2. `/speckit:specify`
3. Optionally, `/speckit:clarify`
4. `/speckit:plan`
5. Optionally, `/speckit:checklist`
6. `/speckit:tasks`
7. Optionally, `/speckit:analyze`
8. `/speckit:implement`
9. Optionally, `/speckit:converge`
