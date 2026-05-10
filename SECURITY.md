# Security Policy

Mnemosyne stores personal and project-specific memory. Treat its databases and local configuration as private runtime data.

## Supported Versions

Security fixes target the latest public version on `main`.

## Reporting a Vulnerability

Please open a private security advisory on GitHub if available, or contact the maintainer through the repository profile.

Do not include real API keys, personal data, or private database dumps in public issues.

## Sensitive Files

The following files should not be committed:

- `graph.db`
- `dream_log.db`
- `llm_config.json`
- runtime backups such as `graph.db.bak-*`
- generated hot/warm/cold memory content with private data

## Design Notes

- Core usage is local-first.
- LLM review is optional.
- Example configs must use environment variables, not real API keys.
- Skill approval requires evidence and governance checks; dry-run scoring is not enough.
