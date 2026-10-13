# Releasing

`yt-demand-dl` publishes to PyPI with GitHub Actions and PyPI Trusted
Publishing (OIDC). No API tokens are stored in the repository or in GitHub
secrets; the workflow mints a short-lived token from PyPI at publish time.

## One-Time Setup (maintainer)

Trusted publishing must be registered on PyPI once before the first release.

1. Create the project on PyPI (or use a pending publisher for the first
   release): https://pypi.org/manage/account/publishing/
2. Add a **pending publisher** with these values:
   - PyPI Project Name: `yt-demand-dl`
   - Owner: `ecoreal`
   - Repository name: `yt-demand-dl`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. In the GitHub repository, create an environment named `pypi`
   (Settings → Environments). Optionally add required reviewers so a human
   approves each publish.

## Cutting a Release

1. Update `version` in `pyproject.toml`.
2. Add release notes to the GitHub Release.
3. Verify the build locally in a throwaway environment:

   ```bash
   python3 -m venv /tmp/ydd-build && /tmp/ydd-build/bin/pip install -q build twine
   /tmp/ydd-build/bin/python -m build
   /tmp/ydd-build/bin/python -m twine check dist/*
   ```

4. Confirm the wheel installs clean and the console scripts resolve:

   ```bash
   python3 -m venv /tmp/ydd-smoke && /tmp/ydd-smoke/bin/pip install -q dist/*.whl
   /tmp/ydd-smoke/bin/yt-demand-dl --help
   /tmp/ydd-smoke/bin/ytdemand --help
   ```

5. Tag and push the tag, then publish a GitHub Release for that tag.
   Publishing the release triggers `publish.yml`, which builds again on a
   clean runner and uploads to PyPI.
