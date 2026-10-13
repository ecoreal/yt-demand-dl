# Contributing

Thanks for improving `yt-demand-dl`.

## Development setup

No dependencies are needed for the offline test suite; the package itself is
standard-library only. `yt-dlp` is an optional extra used by real downloads.

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests
```

`ruff` (config in `pyproject.toml`, `select = ["F", "E9", "B"]`) is the lint
gate CI runs:

```bash
python3 -m pip install ruff
ruff check .
```

## Pull requests

- Keep changes focused; one behavior change per PR.
- Add or update tests for behavior changes. Every offline test must run
  without network access; real-download tests stay behind the
  `YT_DEMAND_DL_RUN_NETWORK=1` opt-in.
- Update the README when CLI flags or behavior change.
- Do not commit downloaded media, archives, or manifests (`data/` and
  `downloads/` are ignored on purpose).

See `.github/PULL_REQUEST_TEMPLATE.md` for the checklist CI mirrors.

## Scope

This project intentionally does not implement YouTube extraction. Extraction,
format selection, and network behavior belong to `yt-dlp`; here we only
orchestrate demands (categories, manifests, constraints) around it. PRs that
reimplement extraction will be redirected to `yt-dlp`.

Download only content you have the right to store, and follow YouTube's terms
and each video's license.
