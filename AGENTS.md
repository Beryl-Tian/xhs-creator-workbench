# Repository rules

## Privacy

- Never commit real creator profiles, notes, comments, transcripts, brand briefs, feedback, oral scripts, publication copy, access tokens, cookies, or credentials.
- Write runtime facts only under `/.xhs-agent/` and rendered local pages only under `/workbench/`.
- Use synthetic, anonymized fixtures under `/tests/fixtures/`.
- Load TikHub credentials only from `TIKHUB_API_TOKEN` or `~/.config/xhs-agent/config.json`.
- Run `python3 scripts/check_privacy.py` before staging or committing.

## Product boundaries

- Treat JSON under `/.xhs-agent/` as the source of truth and HTML as a rebuildable projection.
- Preserve immutable versions and submission snapshots; do not overwrite historical project artifacts.
- Do not promote learning candidates into a creator baseline without explicit user confirmation.
- Keep the Skill entry concise and route task details through its direct references.

## Development

- Support Python 3.11 or newer.
- Keep deterministic file, validation, versioning, diff, and rendering behavior in `src/xhs_agent/`.
- Keep AI workflow instructions in `packages/xhs-creator-workbench/`.
- Add or update tests with behavior changes.
