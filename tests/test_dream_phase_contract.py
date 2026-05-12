#!/usr/bin/env python3
"""Deterministic contract tests for Dream phases.

These tests use a tiny in-memory store so phase behavior is fixed and does not
depend on the live graph.db.
"""

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from core.dream_pipeline import AuditPhase, CausalPhase, ConceptPhase, DecayPhase, TransfersPhase


class DummyEmbedder:
    def encode(self, text):
        seed = sum(ord(ch) for ch in text) or 1
        vec = np.array([seed % 7 + 1, seed % 11 + 1, seed % 13 + 1], dtype=np.float32)
        return vec / np.linalg.norm(vec)


class MemoryStore:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.next_node = 1
        self.next_edge = 1

    def add_node(self, **fields):
        node_id = fields.pop("id", f"n{self.next_node}")
        self.next_node += 1
        node = {
            "id": node_id,
            "type": fields.pop("type", fields.pop("node_type", "experience")),
            "content": fields.pop("content", ""),
            "principle": fields.pop("principle", None),
            "task_type": fields.pop("task_type", None),
            "tier": fields.pop("tier", "hot"),
            "vector": fields.pop("vector", np.array([1, 0, 0], dtype=np.float32).tobytes()),
            "metadata": fields.pop("metadata", {}),
            "last_access": fields.pop("last_access", "2026-05-12T00:00:00+00:00"),
            "access_count": fields.pop("access_count", 0),
            "base_score": fields.pop("base_score", 0.8),
            "half_life_days": fields.pop("half_life_days", 30.0),
            "verified_count": fields.pop("verified_count", 0),
            "confidence": fields.pop("confidence", 1.0),
            "decay_score": fields.pop("decay_score", 1.0),
        }
        node.update(fields)
        self.nodes[node_id] = node
        return node_id

    def add_raw_node(self, **fields):
        return self.add_node(**fields)

    def add_edge(self, from_id, to_id, relation_type, weight=0.5, source="auto", **kwargs):
        if any(e for e in self.edges.values() if e["from_id"] == from_id and e["to_id"] == to_id and e["relation_type"] == relation_type):
            return ""
        edge_id = f"e{self.next_edge}"
        self.next_edge += 1
        self.edges[edge_id] = {
            "id": edge_id,
            "from_id": from_id,
            "to_id": to_id,
            "relation_type": relation_type,
            "weight": weight,
            "source": source,
            "status": kwargs.get("status", "active"),
            "graph_dim": kwargs.get("graph_dim", "semantic"),
            "strength": kwargs.get("strength", "strong"),
        }
        return edge_id

    def bulk_add_edges(self, edges):
        added = 0
        for edge in edges:
            if self.add_edge(**edge):
                added += 1
        return added

    def bulk_get_edge_pairs(self, relation_type):
        return {(e["from_id"], e["to_id"]) for e in self.edges.values() if e["relation_type"] == relation_type and e["status"] == "active"}

    def bulk_update_decay(self, updates):
        for update in updates:
            self.nodes[update["id"]].update(update)
        return len(updates)

    def count_nodes(self):
        return len(self.nodes)

    def count_edges(self):
        return len(self.edges)

    def count_nodes_where(self, where_clause="", params=()):
        return len(self.query_nodes(where_clause, params))

    def query_nodes(self, where_clause="", params=()):
        nodes = list(self.nodes.values())
        if where_clause == "type='experience' AND tier != 'cold'":
            return [n for n in nodes if n.get("type") == "experience" and n.get("tier") != "cold"]
        if where_clause == "type='concept'":
            return [n for n in nodes if n.get("type") == "concept"]
        if where_clause == "type='strategy'":
            return [n for n in nodes if n.get("type") == "strategy"]
        if where_clause == "type='raw' AND tier != 'cold'":
            return [n for n in nodes if n.get("type") == "raw" and n.get("tier") != "cold"]
        if where_clause == "type='experience' AND task_type IS NULL":
            return [n for n in nodes if n.get("type") == "experience" and not n.get("task_type")]
        if where_clause == "type='experience'":
            return [n for n in nodes if n.get("type") == "experience"]
        return nodes

    def query_edges(self, where_clause="", params=()):
        edges = list(self.edges.values())
        if where_clause == "relation_type='is_a' AND status='active'":
            return [e for e in edges if e["relation_type"] == "is_a" and e["status"] == "active"]
        if where_clause == "relation_type='caused' AND status='active'":
            return [e for e in edges if e["relation_type"] == "caused" and e["status"] == "active"]
        if where_clause == "relation_type='solves' AND status='active'":
            return [e for e in edges if e["relation_type"] == "solves" and e["status"] == "active"]
        if where_clause == "relation_type='transfers_to' AND status='active'":
            return [e for e in edges if e["relation_type"] == "transfers_to" and e["status"] == "active"]
        if where_clause == "source='auto' AND status='active'":
            return [e for e in edges if e["source"] == "auto" and e["status"] == "active"]
        if where_clause == "source='dream' AND status='active'":
            return [e for e in edges if e["source"] == "dream" and e["status"] == "active"]
        return edges

    def get_node(self, node_id):
        return self.nodes.get(node_id)


def unit_vec(values):
    vec = np.array(values, dtype=np.float32)
    return (vec / np.linalg.norm(vec)).tobytes()


class DreamPhaseContractTests(unittest.TestCase):
    def test_causal_phase_requires_structured_evidence(self):
        store = MemoryStore()
        problem = store.add_node(
            id="problem",
            content="gzip JSON parse failed",
            task_type="api_proxy",
            vector=unit_vec([1, 0, 0]),
            metadata={"outcome": "failure", "problem": "gzip parse failed", "entities": ["gzip", "json"]},
        )
        solution = store.add_node(
            id="solution",
            content="decompress gzip before JSON.parse",
            task_type="api_proxy",
            vector=unit_vec([0.99, 0.01, 0]),
            metadata={"outcome": "success", "solution": "gunzip first", "entities": ["gzip", "json"]},
        )
        store.add_node(
            id="near-but-unstructured",
            content="similar text without metadata",
            task_type="api_proxy",
            vector=unit_vec([0.99, 0.01, 0]),
            metadata={},
        )

        result = CausalPhase().run(store, DummyEmbedder())

        self.assertEqual(result["added"], 1)
        self.assertEqual(store.edges["e1"]["from_id"], solution)
        self.assertEqual(store.edges["e1"]["to_id"], problem)
        self.assertEqual(store.edges["e1"]["relation_type"], "solves")
        self.assertEqual(store.edges["e1"]["graph_dim"], "causal")

    def test_concept_and_transfers_use_cross_task_clusters(self):
        store = MemoryStore()
        for node_id, task in (("a", "api_proxy"), ("b", "debugging"), ("c", "testing")):
            store.add_node(
                id=node_id,
                content=f"{task} evidence",
                principle="Check encoding before parsing",
                task_type=task,
                vector=unit_vec([1, 0, 0]),
            )

        concept_result = ConceptPhase().run(store, DummyEmbedder())
        transfer_result = TransfersPhase().run(store, DummyEmbedder())

        self.assertEqual(concept_result["concepts_created"], 1)
        self.assertEqual(concept_result["is_a_added"], 3)
        self.assertEqual(transfer_result["added"], 3)
        self.assertTrue(all(e["relation_type"] == "transfers_to" for e in list(store.edges.values())[3:]))

    def test_decay_keeps_cold_raw_cold(self):
        store = MemoryStore()
        store.add_node(id="raw-cold", type="raw", tier="cold", decay_score=0, base_score=2.0, access_count=20)
        store.add_node(id="active", type="experience", tier="warm", decay_score=0.1, base_score=0.8)

        result = DecayPhase().run(store, DummyEmbedder())

        self.assertEqual(result["updated"], 1)
        self.assertEqual(store.nodes["raw-cold"]["tier"], "cold")
        self.assertEqual(store.nodes["raw-cold"]["decay_score"], 0)

    def test_audit_warns_on_health_contracts(self):
        store = MemoryStore()
        for i in range(21):
            store.add_node(id=f"raw-{i}", type="raw", tier="hot")
        audit = AuditPhase()
        audit.set_snapshot({"node_cap": 200, "edge_cap": 500})

        result = audit.run(store, DummyEmbedder())

        self.assertEqual(result["status"], "WARN")
        self.assertTrue(any("raw 待蒸馏积压" in alert for alert in result["alerts"]))


if __name__ == "__main__":
    unittest.main()
