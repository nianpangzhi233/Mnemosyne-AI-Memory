# Benchmarks

This page explains what Mnemosyne is trying to optimize for.

## What to measure

- Retrieval quality across repeated sessions.
- Token savings from layered memory.
- Prediction accuracy for `precondition`-based memories.
- Dream-cycle consolidation quality.
- Skill trigger precision and false-positive rate.

## Current design claims

| Capability | Mnemosyne design goal |
|------------|------------------------|
| L0/L1/L2 retrieval | Fast relevance checking with smaller prompt cost |
| Predictive memory | Remember when a memory applies, not just what it says |
| Dream consolidation | Discover relations and prune weak noise automatically |
| Skill governance | Prevent untested skills from entering default injection |

## Why this page exists

People trust open source projects faster when they can see what is being measured. This page is here so future benchmark numbers have a home instead of being buried in release notes.

## Suggested future benchmark sections

- Search latency by mode
- Token savings versus plain prompt memory
- Dashboard startup time
- Skill promotion false-positive rate
- Dream cycle duration
