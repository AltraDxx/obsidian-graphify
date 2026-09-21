# Contributing

## Branches

- `main` is the stable public branch. It must pass the full validation suite.
- `develop` integrates the next stable version.
- Use short-lived `feature/*`, `fix/*`, `docs/*`, `refactor/*`, or `chore/*` branches from `develop`.
- Create `hotfix/*` from `main`, then merge the result back into `develop`.

Prefer squash merges from topic branches into `develop`. Promote `develop` to `main` through a pull request and tag stable releases.

## Public repository boundary

Do not commit vault contents, evidence, logs, generated exports, local Obsidian state, Smart Connections indexes, credentials, or media. The root `.gitignore` defines the enforced boundary.

## Validation

Run before committing:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/graphify.py lint
python3 scripts/graphify.py status
git diff --check
```

The first two commands must exit successfully. Lint warnings may remain when they describe review work rather than structural errors.

## Commits

Keep each commit focused and use one of these prefixes when natural:

- `feat:` new behavior
- `fix:` defect correction
- `docs:` documentation only
- `test:` test coverage
- `refactor:` internal restructuring
- `chore:` repository or maintenance work
