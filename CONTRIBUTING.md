# Contributing

How we work together on this repository.

## Workflow

1. Run `git pull` before starting work and again before pushing.
2. Push your work directly to `main` at least once per week.
3. The other team member reviews the pushed changes (reads the code and runs it locally) and gives feedback.
4. Never commit credentials, `.env` files or datasets (see `.gitignore`).

## Commit message convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) convention:

```
<type>(<optional scope>): <short description>
```

- Write the description in the imperative ("add", not "added"), lowercase, without a trailing period.
- Keep the first line under about 72 characters; add a body after a blank line if more explanation is needed.

### Types

| Type | Use for |
|---|---|
| `feat` | A new feature or pipeline step |
| `fix` | A bug fix |
| `docs` | Documentation only (README, architecture, data sources) |
| `refactor` | Code change that neither adds a feature nor fixes a bug |
| `test` | Adding or changing tests or data-quality checks |
| `chore` | Maintenance: dependencies, `.gitignore`, config, cleanup |
| `build` | Docker, Docker Compose or dependency setup |
| `ci` | Automation workflows (e.g. GitHub Actions) |
| `style` | Formatting only, no change in behaviour |
| `perf` | Performance improvements |

### Scopes (optional)

`transport`, `weather`, `stops`, `orchestration`, `transform`, `terraform`, `dashboard`, `docs`

### Examples

```
feat(transport): add daily Ist-Daten ingestion into PostgreSQL
fix(weather): convert MeteoSwiss timestamps from UTC to local time
docs: add architecture v0.1 and data source description
build: add PostgreSQL service to docker-compose
chore: ignore .idea folder
feat(orchestration): add backfill for monthly Ist-Daten archive
```
