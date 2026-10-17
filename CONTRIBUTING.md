# Contributing — SafeZone

## Commit messages

Format: `type(scope): short description`

- Lowercase after the colon, no trailing period
- Imperative mood: "add", not "added" or "adds"
- Under ~72 characters for the subject line
- One logical change per commit

### Types

| Type | When to use | Example |
|---|---|---|
| `feat` | New feature or endpoint | `feat(weather): integrate open-meteo batch polling loop` |
| `fix` | Bug or unexpected behaviour | `fix(map): resolve leaflet marker duplication on refresh` |
| `docs` | Documentation or setup instructions | `docs(readme): add quick-start test script instructions` |
| `style` | Formatting only, no code change | `style(ui): format priority queue alignment and padding` |
| `refactor` | Neither fixes a bug nor adds a feature | `refactor(agent): extract prompt templates into separate module` |
| `chore` | Build process, tooling, dependencies | `chore(deps): add fastapi and uvicorn dependencies` |
| `test` | Adding or fixing tests | `test(phone): cover 00 international prefix` |

### Scopes

Use the module or area touched:

`phone`, `config`, `db`, `schema`, `events`, `whatsapp`, `intake`, `tools`,
`agent`, `protocol`, `risk`, `hazards`, `dispatch`, `silence`, `seed`,
`ui`, `map`, `queue`, `responder`, `deps`, `readme`

Omit the scope if a change genuinely spans the whole repo: `chore: add gitignore rules`

### Examples from this project


## Branches

Short-lived branches off `main`, merged the same day.

Name as `type/short-description`: `feat/volunteer-commands`, `fix/phone-prefix`

A branch that lives longer than a few hours during a hackathon becomes a merge
conflict. Commit small, merge often.

## Pull requests

- One review from a senior (Salman or Hussain) before merge
- Nothing reaches prod without Salman, who holds the prod keys

## Before every commit

- [ ] No real phone numbers in any file (see AGENTS.md section 12)
- [ ] No `.env`, `*.db`, or `Backend/static/` in the diff
- [ ] Tests pass: `cd Backend && python -m pytest -q`