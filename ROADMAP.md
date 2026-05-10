# Roadmap

Mnemosyne is built around one goal: make AI agents keep useful experience across sessions without turning memory into a noisy prompt dump.

## Current Focus

- v7 skill evidence flow: automatic post-dream skill scanning, conservative evolution, trial feedback, and promotion gates.
- Dashboard visibility: make memory health, dream runs, and skill evidence easy to inspect.
- Open-source packaging: clearer onboarding, GitHub Pages, CI, issue templates, and release hygiene.

## Next

- Public demo dataset with safe, non-personal memories.
- Better dashboard screenshots and short demo video.
- More MCP client examples for OpenCode, Claude Desktop, and Cursor-style tools.
- Skill evolution history page instead of only the latest daemon summary.
- Lightweight benchmark suite for retrieval quality, token savings, and trigger precision.

## Later

- Optional Neo4j or external graph-store adapter.
- More embedding provider adapters.
- Pluggable privacy policy engine for enterprise-style deployments.
- Better multilingual examples and documentation.

## Non-goals

- Mnemosyne is not a hosted SaaS memory service.
- Mnemosyne is not a generic browser or desktop automation agent.
- Mnemosyne does not approve generated skills without evidence.
