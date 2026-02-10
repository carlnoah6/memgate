"""
CLI Entry Point — python -m memgate.red_team

Runs red-blue adversarial testing and outputs JSON/Markdown reports.
"""

import argparse
import json

from .arena import Arena
from .strategies import list_strategies


def main():
    parser = argparse.ArgumentParser(
        prog="memgate.red_team",
        description="MemGate Red Team Arena — LLM adversarial testing framework",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="Number of adversarial rounds (default: 10)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="all",
        help="Attack strategy: "
        + ", ".join(list_strategies())
        + ", all (default: all)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default="https://api.openai.com/v1",
        help="LLM API base URL",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="LLM API key",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock mode (no real LLM calls)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output report to file (default: stdout)",
    )
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    if not args.mock and not args.api_key:
        parser.error("--api-key is required when not using --mock mode")

    arena = Arena(
        rounds=args.rounds,
        strategy=args.strategy,
        mock=args.mock,
        api_base=args.api_base,
        api_key=args.api_key,
        verbose=args.verbose,
    )

    report_dict = arena.run()

    if args.format == "markdown":
        output_text = arena.report_gen.report.to_markdown()
    else:
        output_text = json.dumps(report_dict, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_text)
        if args.verbose:
            print(f"\n📄 Report saved to: {args.output}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
