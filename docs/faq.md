# FAQ

## What is Mnemosyne?

Mnemosyne is a local-first AI memory system that combines GraphRAG, vector search, predictive memory, dream consolidation, and governed Skill Memory.

## How is this different from a normal RAG app?

Normal RAG answers a query from retrieved chunks. Mnemosyne also stores experience with preconditions, predicts when a memory applies, discovers relations during dream cycles, and can evolve reusable skills after evidence-based checks.

## Do I need external services?

No for the core path. Mnemosyne works locally with SQLite and local embeddings. Optional LLM review can be enabled if you want deeper distillation or skill development.

## What can I do with it?

- Remember project decisions and lessons across sessions.
- Search by vector, keyword, graph relation, or tags.
- Run dream cycles to consolidate and clean the graph.
- Grow governed skills from stable experience clusters.
- Inspect everything in the dashboard.

## Who is it for?

- Developers building AI assistants or agent workflows.
- Teams who keep repeating the same explanations to their tools.
- People who want a memory system they can inspect instead of a black box.

## Is it hard to run?

The intended path is:

```bash
python setup.py
```

Then optionally start the API, dashboard, and dream cycle separately.

## Does it work offline?

Yes, for the core local memory path. That is one of the main goals of the project.

## Where should I start?

- Read the [Quick Start](../README.md#quick-start)
- Open the [Project Site](https://nianpangzhi233.github.io/Mnemosyne-AI-Memory/)
- Skim [Why it matters](why-it-matters.md)
- Check [Benchmarks](benchmarks.md)
