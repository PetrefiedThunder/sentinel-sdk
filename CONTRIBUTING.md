# Contributing to Sentinel (Python SDK)

Thanks for considering a contribution. Bug reports, feature ideas, and
PRs are all welcome.

## Quick start

```bash
git clone https://github.com/PetrefiedThunder/sentinel-sdk
cd sentinel-sdk
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Filing a bug

Open an issue at https://github.com/PetrefiedThunder/sentinel-sdk/issues
and include:

1. SDK version (`python -c "import sentinel; print(sentinel.__version__)"`)
2. Python version and OS
3. A minimal reproducible example (10–20 lines)
4. The full traceback / error message

## Pull requests

1. Open an issue first if it's a behavior change — saves you wasted work.
2. Branch from `main`. Small, focused PRs over large ones.
3. Add a test that fails before your fix and passes after.
4. Run `pytest` and `ruff check .` before pushing.
5. Update `CHANGELOG.md` under an `## [Unreleased]` heading.

## Releasing (maintainers only)

1. Bump `version` in `pyproject.toml`, `sentinel/__init__.py`,
   and the `USER_AGENT` constant in `sentinel/client.py`.
2. Move `## [Unreleased]` notes into a versioned section in
   `CHANGELOG.md` with today's date.
3. Commit, tag `vX.Y.Z`, push tags. GitHub Actions ships to PyPI via
   Trusted Publishing.

## Security

If you find a security issue, please email security@regengine.co —
do **not** file a public GitHub issue.

## Code of conduct

Be excellent to each other. Bigoted, harassing, or otherwise antisocial
behavior gets you removed from the project.
