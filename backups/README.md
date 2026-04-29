# Local backups

This directory is for local production backup artifacts that should be easy to
find from the repo but should not be committed to git.

Current Render retirement archive:

```text
backups/bideuchre-retire-backup-20260429.tar.gz
```

The same archive is also stored in iCloud Drive:

```text
/Users/claude_runner/Library/Mobile Documents/com~apple~CloudDocs/Bid-Euchre Backups/bideuchre-retire-backup-20260429.tar.gz
```

The `.tar.gz` contains production hosted-play data: players, invite codes,
comments, match links, hands, and decisions. It is intentionally ignored by
git. Commit the checksum and documentation, not the data archive.

See `docs/01_core/RENDER_RETIREMENT_2026-04-29.md` for validation and restore
instructions.
