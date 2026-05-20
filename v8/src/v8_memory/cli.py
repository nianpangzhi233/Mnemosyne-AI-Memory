from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .context import ContextPackBuilder
from .lifecycle import LifecycleManager
from .services import CandidateWriter, EventWriter, EvidenceRecorder
from .store import SQLiteV8Store


def _json_arg(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON: {exc.msg}") from exc


def _scope_from_args(args) -> dict:
    scope = dict(getattr(args, "scope", {}) or {})
    for item in getattr(args, "scope_item", []) or []:
        if "=" not in item:
            raise ValueError(f"invalid scope item: {item}")
        key, value = item.split("=", 1)
        if not key or not value:
            raise ValueError(f"invalid scope item: {item}")
        scope[key] = value
    return scope


def _add_scope_args(parser, required_json: bool = False) -> None:
    parser.add_argument("--scope", type=_json_arg, default={} if not required_json else None, required=required_json)
    parser.add_argument("--scope-item", action="append", default=[], help="Scope as key=value; repeatable and PowerShell-friendly")


def _print_json(result, pretty: bool = False) -> None:
    kwargs = {"ensure_ascii": True, "sort_keys": True}
    if pretty:
        kwargs["indent"] = 2
    print(json.dumps(result, **kwargs))


def _add_event_parser(sub):
    event = sub.add_parser("add")
    event.add_argument("--type", required=True)
    event.add_argument("--actor", required=True)
    event.add_argument("--content", required=True)
    _add_scope_args(event)
    get = sub.add_parser("get")
    get.add_argument("--id", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=20)
    return event


def _add_candidate_parser(sub):
    cand = sub.add_parser("add")
    cand.add_argument("--type", required=True)
    cand.add_argument("--content", required=True)
    cand.add_argument("--sources", nargs="+", required=True)
    _add_scope_args(cand)
    cand.add_argument("--trigger", required=True)
    cand.add_argument("--risk", default="low")
    get = sub.add_parser("get")
    get.add_argument("--id", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=20)
    return cand


def _add_evidence_parser(sub):
    ev = sub.add_parser("add")
    ev.add_argument("--target", required=True)
    ev.add_argument("--target-type", default="candidate")
    ev.add_argument("--type", required=True)
    ev.add_argument("--polarity", required=True)
    ev.add_argument("--content", required=True)
    ev.add_argument("--sources", nargs="*", default=[])
    get = sub.add_parser("get")
    get.add_argument("--id", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.add_argument("--target-type")
    list_cmd.add_argument("--target")
    return ev



def _add_lifecycle_parsers(sub):
    promote = sub.add_parser("promote")
    promote.add_argument("--candidate", required=True)
    for action in ("demote", "deprecate", "stale"):
        parser = sub.add_parser(action)
        parser.add_argument("--memory", required=True)
    return promote



def _add_context_parser(sub):
    ctx = sub.add_parser("build")
    ctx.add_argument("--task", required=True)
    _add_scope_args(ctx)
    get = sub.add_parser("get")
    get.add_argument("--id", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=20)
    return ctx


def _add_memory_parser(sub):
    get = sub.add_parser("get")
    get.add_argument("--id", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=20)
    return get


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="v8-memory")
    parser.add_argument("--db", default=str(Path("v8/data/v8.db")))
    parser.add_argument("--pretty", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    event_cmd = sub.add_parser("event")
    _add_event_parser(event_cmd.add_subparsers(dest="action", required=True))

    candidate_cmd = sub.add_parser("candidate")
    _add_candidate_parser(candidate_cmd.add_subparsers(dest="action", required=True))

    evidence_cmd = sub.add_parser("evidence")
    _add_evidence_parser(evidence_cmd.add_subparsers(dest="action", required=True))

    lifecycle_cmd = sub.add_parser("lifecycle")
    _add_lifecycle_parsers(lifecycle_cmd.add_subparsers(dest="action", required=True))

    memory_cmd = sub.add_parser("memory")
    _add_memory_parser(memory_cmd.add_subparsers(dest="action", required=True))

    context_cmd = sub.add_parser("context")
    _add_context_parser(context_cmd.add_subparsers(dest="action", required=True))

    # Legacy flat commands kept while tests and scripts migrate.
    legacy_event = sub.add_parser("event-add")
    legacy_event.set_defaults(action="add")
    legacy_event.add_argument("--type", required=True)
    legacy_event.add_argument("--actor", required=True)
    legacy_event.add_argument("--content", required=True)
    _add_scope_args(legacy_event)

    legacy_cand = sub.add_parser("candidate-add")
    legacy_cand.set_defaults(action="add")
    legacy_cand.add_argument("--type", required=True)
    legacy_cand.add_argument("--content", required=True)
    legacy_cand.add_argument("--sources", nargs="+", required=True)
    _add_scope_args(legacy_cand)
    legacy_cand.add_argument("--trigger", required=True)
    legacy_cand.add_argument("--risk", default="low")

    legacy_ev = sub.add_parser("evidence-add")
    legacy_ev.set_defaults(action="add")
    legacy_ev.add_argument("--target", required=True)
    legacy_ev.add_argument("--target-type", default="candidate")
    legacy_ev.add_argument("--type", required=True)
    legacy_ev.add_argument("--polarity", required=True)
    legacy_ev.add_argument("--content", required=True)
    legacy_ev.add_argument("--sources", nargs="*", default=[])

    legacy_promote = sub.add_parser("promote")
    legacy_promote.set_defaults(action="promote")
    legacy_promote.add_argument("--candidate", required=True)

    for action in ("demote", "deprecate", "stale"):
        legacy = sub.add_parser(action)
        legacy.set_defaults(action=action)
        legacy.add_argument("--memory", required=True)

    legacy_ctx = sub.add_parser("context-build")
    legacy_ctx.set_defaults(action="build")
    legacy_ctx.add_argument("--task", required=True)
    _add_scope_args(legacy_ctx)

    args = parser.parse_args(argv)
    try:
        store = SQLiteV8Store(args.db)
        if args.cmd in {"event", "event-add"}:
            if args.action == "add":
                result = {"id": EventWriter(store).add(args.type, args.actor, args.content, _scope_from_args(args))}
            elif args.action == "get":
                result = store.inspect_get("raw_events", args.id)
            else:
                result = {"items": store.inspect_list("raw_events", args.limit)}
        elif args.cmd in {"candidate", "candidate-add"}:
            if args.action == "add":
                result = {"id": CandidateWriter(store).add(args.type, args.content, args.sources, _scope_from_args(args), args.trigger, args.risk)}
            elif args.action == "get":
                result = store.inspect_get("candidates", args.id)
            else:
                result = {"items": store.inspect_list("candidates", args.limit)}
        elif args.cmd in {"evidence", "evidence-add"}:
            if args.action == "add":
                result = {"id": EvidenceRecorder(store).add(args.target_type, args.target, args.type, args.polarity, args.content, args.sources)}
            elif args.action == "get":
                result = store.inspect_get("evidence", args.id)
            elif args.target_type and args.target:
                result = {"items": store.inspect_evidence_for_target(args.target_type, args.target)}
            else:
                result = {"items": store.inspect_list("evidence", args.limit)}
        elif args.cmd in {"lifecycle", "promote", "demote", "deprecate", "stale"}:
            lifecycle = LifecycleManager(store)
            if args.action == "promote":
                result = {"id": lifecycle.promote(args.candidate)}
            elif args.action == "demote":
                result = {"id": lifecycle.demote(args.memory)}
            elif args.action == "deprecate":
                result = {"id": lifecycle.deprecate(args.memory)}
            else:
                result = {"id": lifecycle.stale(args.memory)}
        elif args.cmd == "memory":
            if args.action == "get":
                result = store.inspect_get("memories", args.id)
            else:
                result = {"items": store.inspect_list("memories", args.limit)}
        else:
            if args.action == "build":
                result = ContextPackBuilder(store).build(args.task, _scope_from_args(args))
            elif args.action == "get":
                result = store.inspect_get("context_pack_runs", args.id)
            else:
                result = {"items": store.inspect_list("context_pack_runs", args.limit)}
        _print_json(result, args.pretty)
        return 0
    except Exception as exc:
        _print_json({"error": str(exc), "type": exc.__class__.__name__}, args.pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
