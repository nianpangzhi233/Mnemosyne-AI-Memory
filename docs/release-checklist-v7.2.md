# v7.2 Release Checklist

Use this before publishing the GitHub release. It intentionally separates local verification from public GitHub actions.

## Local Verification

- [ ] `python -m py_compile scripts\skill_daemon.py scripts\dashboard\pages\dashboard.py scripts\graph_dream.py scripts\graph_query.py scripts\graph_write.py scripts\graph_audit.py`
- [ ] `python scripts\skill_daemon.py --once`
- [ ] Dashboard opens with `streamlit run scripts/dashboard/app.py --server.port 8501`
- [ ] README links are correct.
- [ ] GitHub Pages workflow references `site/index.html` and `assets/`.
- [ ] `assets/social-preview.png` exists.

## Privacy / Repository Safety

- [ ] No `graph.db` staged.
- [ ] No `dream_log.db` staged.
- [ ] No `llm_config.json` staged.
- [ ] No private memory dumps from `hot/`, `warm/`, `cold/`, `proposals/`, or `reflections/` staged.
- [ ] No real API keys in configs, docs, screenshots, or release notes.

## GitHub Settings

- [x] Repository description updated.
- [x] Homepage set to GitHub Pages URL.
- [x] Topics added.
- [x] Discussions enabled.
- [ ] Upload `assets/social-preview.png` in Settings -> General -> Social preview.
- [ ] Enable Pages source: GitHub Actions.

## Release

- [ ] Commit v7 feature changes separately from open-source packaging changes.
- [ ] Push `main`.
- [ ] Confirm CI passes.
- [ ] Confirm Pages deploys.
- [ ] Publish GitHub release using `docs/releases/v7.2.0.md`.
- [ ] Tag as `v7.2.0`.
