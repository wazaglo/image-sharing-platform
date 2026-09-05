# Contributing to ImageShare

Thank you for considering contributing to ImageShare! We welcome contributions of all kinds: bug fixes, features, documentation, and tests.

## How to Contribute

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes
4. Run linting and tests
5. Commit using Conventional Commits
6. Push and open a Pull Request

## Development Setup

```bash
git clone <repo-url> image-sharing-platform
cd image-sharing-platform
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

## Code Style

- Follow PEP 8 guidelines
- Use [Black](https://github.com/psf/black) with default settings for code formatting
- Use [isort](https://github.com/PyCQA/isort) with `--profile=black` for import sorting
- Maximum line length: 120 characters
- Use type hints for all function signatures
- Write docstrings for public functions and classes

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:`. A new feature
- `fix:`. A bug fix
- `docs:`. Documentation changes
- `chore:`. Maintenance tasks
- `refactor:`. Code restructuring without feature/bug changes
- `test:`. Adding or updating tests
- `ci:`. CI/CD configuration changes

Examples:
```
feat: add folder upload via webkitdirectory
fix: resolve race condition in thumbnail generation
docs: update API reference with new endpoints
```

## Pull Request Process

1. Ensure all existing tests pass
2. Add tests for new functionality
3. Update documentation if needed (README, API docs, architecture docs)
4. Run `make lint` and fix any issues
5. Update CHANGELOG.md under the `[Unreleased]` section
6. Request review from at least one maintainer
7. Address all review feedback before merging

## Testing Requirements

- All new features must include unit tests
- Test files go in the `tests/` directory mirroring the `src/` structure
- Use pytest fixtures for common setup
- Mock AWS services (boto3) in unit tests, never hit real APIs
- Tests are run with `make test` or `python -m pytest tests/ -v`
- Aim for at least 80% code coverage on new code

## CI/CD

The project uses GitHub Actions for CI/CD. There are two workflows:

- `deploy.yml`. Runs lint and test on all PRs and pushes; deploys to dev (develop branch) or prod (main branch)
- `test.yml`. Runs tests on PRs across Python 3.10 and 3.11

All PR checks must pass before merging.
