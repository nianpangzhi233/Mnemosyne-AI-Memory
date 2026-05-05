# Contributing to Mnemosyne

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourname/mnemosyne.git`
3. Run setup: `python setup.py`
4. Create a branch: `git checkout -b feature/your-feature`

## Development Guidelines

### Code Style

- Follow PEP 8
- Use type hints for function signatures
- Keep functions focused — one function, one responsibility
- No unnecessary comments — code should be self-documenting

### Architecture Principles

- All components go through abstract interfaces (`AbstractGraphStore`, `AbstractEmbedder`, `AbstractTaskRunner`)
- Dream phases are plug-in classes inheriting `DreamPhase`
- No direct SQL in upper-layer scripts — use the store interface
- Set `HF_HUB_OFFLINE=1` in any script that loads models

### Adding a New Embedder

```python
# scripts/core/embedder.py
class MyEmbedder(_SentenceTransformerEmbedder):
    MODEL_NAME = "my-org/my-model"
```

Then register it in `scripts/core/__init__.py`.

### Adding a New Dream Phase

```python
# scripts/core/dream_pipeline.py
class MyPhase(DreamPhase):
    @property
    def name(self) -> str:
        return "my phase"

    def run(self, store: AbstractGraphStore, embedder: AbstractEmbedder) -> dict:
        # Your logic here
        return {"result": "ok"}
```

Register in `_ALL_PHASES` list.

### Adding a New GraphStore

Subclass `AbstractGraphStore` and implement all abstract methods. See `sqlite_store.py` as reference.

## Testing

Before submitting a PR:

```bash
# Run full dream cycle
python scripts/graph_dream.py --full

# Check health
python scripts/graph_audit.py

# Test search quality
python scripts/graph_query.py --vector-search "test query" --top 5
```

## Pull Request Process

1. Ensure all existing functionality works
2. Update README.md if adding features
3. Update CHANGELOG.md
4. Keep PRs focused — one feature/fix per PR

## Reporting Issues

- Include Python version and OS
- Include full error traceback
- Describe expected vs actual behavior
