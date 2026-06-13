"""Command line entrypoint for DeepResearch."""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from deep_research.cross_cutting.errors import Fatal
from deep_research.pipeline import Report
from deep_research.runtime import run_research


def main(argv: Sequence[str] | None = None) -> int:
    """Run the DeepResearch CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "research":
        return asyncio.run(_research_command(question=args.question, json_output=args.json))

    parser.print_help(sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deep-research")
    subcommands = parser.add_subparsers(dest="command")

    research = subcommands.add_parser("research", help="run one Plan/Search/Verify/Write task")
    research.add_argument("question", help="open-ended research question")
    research.add_argument("--json", action="store_true", help="print the full Report as JSON")
    return parser


async def _research_command(*, question: str, json_output: bool) -> int:
    try:
        report = await run_research(question)
    except Fatal as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1

    _print_report(report=report, json_output=json_output)
    return 0


def _print_report(*, report: Report, json_output: bool) -> None:
    if json_output:
        print(report.model_dump_json(indent=2))
        return

    print(report.body)
    if report.citations:
        print()
        print("Citations:")
        for index, citation in enumerate(report.citations, start=1):
            print(f"{index}. {citation.url} - {citation.claim}")


if __name__ == "__main__":
    raise SystemExit(main())
