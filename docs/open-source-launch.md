# Open Source Launch Checklist

This checklist keeps the public repository understandable, trustworthy, and easy to share.

## Repository Settings

Recommended GitHub topics:

```text
ai-agent memory graph-rag mcp knowledge-graph vector-search sqlite embeddings skill-evolution agent-memory local-first
```

Recommended repository description:

```text
Bionic memory for AI agents: GraphRAG, predictive memory, dream consolidation, governed skill evolution, MCP, REST API, and dashboard.
```

Recommended homepage:

```text
https://nianpangzhi233.github.io/Mnemosyne-AI-Memory/
```

## Before Publishing a Release

- Update `CHANGELOG.md`.
- Check README badges and version text.
- Run `python -m py_compile` on changed Python scripts.
- Run the daemon once if skill flow changed.
- Ensure no private DB, API key, local config, or personal memory file is staged.
- Publish a matching GitHub release for the current version.

## Assets

- `assets/hero.svg` for README first-screen branding.
- `assets/social-preview.svg` for GitHub social preview upload.
- `assets/social-preview.png` for GitHub social preview upload.
- `assets/architecture.svg` for architecture explanation.
- `assets/dashboard-preview.svg` for README and project-site preview.

Assets still worth adding later:

- Real dashboard screenshot from a clean demo database.
- Real skill evidence-flow screenshot.
- 30-60 second demo GIF or video.

## Suggested Launch Copy

```text
Mnemosyne gives AI agents a local-first memory system: write experiences, retrieve them through GraphRAG, consolidate them during dream cycles, and grow reusable skills only after evidence-based gates.
```

## Release Copy

Use `docs/releases/v7.2.0.md` as the GitHub release body for the next public release.
