# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- `README.zh.md`, a full Chinese translation cross-linked with the English
  README; a test pins section parity and the cross-links.
- MIT `LICENSE` file (the package declared MIT in `pyproject.toml` but the
  repository had no license text, so GitHub showed none).
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, an issue form, and a
  PR template.
- PyPI Trusted Publishing workflow (`publish.yml`) and `docs/releasing.md`;
  no long-lived tokens are stored anywhere.
- Dependabot for weekly `github-actions` updates (the workflows pin actions to
  commit SHAs).

### Fixed

- `verify-ap10k --min-height` no longer crashes on malformed `yt-dlp` info
  JSON (non-object root, mapping-valued `requested_downloads`) or non-UTF-8
  info files; unreadable archives are reported instead of aborting the run.
- Category lists and manifests encoded with a UTF-8 BOM are accepted instead
  of silently yielding a single junk category or rejecting every row.
- `--cookies-from-browser` now follows `yt-dlp`'s documented grammar
  (`browser[:profile][+keyring]`: empty profiles and keyrings are rejected
  with clear errors instead of being silently degraded or forwarded).
- The download-archive regression test no longer assumes a commit order; the
  lock guarantees mutual exclusion only, and the test now proves exactly
  that with a deterministic inversion case.

## 0.1.0

### Added

- Demand-driven download orchestration over `yt-dlp`: single URLs, YouTube
  searches, JSONL manifests, and AP-10K category plans.
- `list-ap10k`, `download`, `download-manifest`, `ap10k`, `resume-ap10k`,
  and `verify-ap10k` commands, plus a small Python API
  (`make_ap10k_jobs`, `build_jobs`, `YtDlpBackend`, `DownloadOptions`).
- Network-free planning mode (`--plan-output`) and `--dry-run` for both
  searches and manifests.
- `verify-ap10k` audit with `--missing-output` for resume workflows.
- Optional `download` extra (`yt-dlp`) so the package imports without the
  engine installed.

### Security

- Output templates are validated to stay inside the configured output root;
  portable path escapes (`..`, backslashes, drive prefixes) are rejected.
- Symlinked manifests, verification inputs, and output paths are refused.
- Manifest and category input are bounded (row count, row size, total size)
  before any network call; download options are validated and outputs are
  written atomically.

### Fixed

- Numeric download options (limits, retries, timeouts) are validated with
  line-aware errors instead of failing deep inside `yt-dlp`.
- Labelled jobs preserve their download options.
