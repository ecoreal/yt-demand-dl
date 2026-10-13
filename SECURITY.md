# Security Policy

## Scope

`yt-demand-dl` orchestrates `yt-dlp` calls from user-provided demands,
manifests, and category files. In scope for security reports:

- Argument/option injection into the `yt-dlp` subprocess through manifest,
  category, or CLI input.
- Path traversal or unsafe file writes when saving downloads, archives, or
  verification output.
- Crashes or state corruption caused by malformed input files (reported as
  robustness bugs when no security impact exists).

Out of scope: vulnerabilities in `yt-dlp` itself (report those upstream) and
site-specific extraction behavior.

## Reporting

Create a private advisory on GitHub ("Report a vulnerability" under the
Security tab) for the repository owner. Please include a minimal reproducer
(command + input file excerpt) and the observed behavior.

Do not open a public issue for an undisclosed vulnerability.
