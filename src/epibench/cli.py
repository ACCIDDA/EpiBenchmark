"""Command-line interface for the `epibench` package."""

from __future__ import annotations

import argparse

from . import __version__


def _add_setup_subcommand(subparsers: argparse._SubParsersAction) -> None:
    """Register the setup command and its options."""
    setup_parser = subparsers.add_parser(
        "setup",
        help="Set up your model runs with ground truth data pulled from specified hub.",
        description="Command to get appropriately vintaged ground truth data to run your model on",
    )
    setup_parser.add_argument(
        "--config-path",
        type=str,
        required=False,
        help="Absolute path to your YAML configuration file.",
    )
    setup_parser.set_defaults(handler=_run_setup)


def _add_score_subcommand(subparsers: argparse._SubParsersAction) -> None:
    """Register the score command placeholder."""
    score_parser = subparsers.add_parser(
        "score",
        help="Score model output against ground truth.",
        description="Command to score (WIS) model forecasts against ground truth data.",
    )
    score_parser.set_defaults(handler=_run_score)


def _add_plot_subcommand(subparsers: argparse._SubParsersAction) -> None:
    """Register the plot command placeholder."""
    plot_parser = subparsers.add_parser(
        "plot",
        help="Generate evaluation plots from scoring output.",
        description="Command to build plots used for evaluation of model forecast data.",
    )
    plot_parser.set_defaults(handler=_run_plot)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="epibench",
        description="Command-line interface for EpiBench pipelines.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")
    _add_setup_subcommand(subparsers)
    _add_score_subcommand(subparsers)
    _add_plot_subcommand(subparsers)
    return parser


def _run_setup(args: argparse.Namespace) -> int:
    """Run the EpiBench setup pipeline."""
    from .setup import setup

    setup(config_path=args.config_path)
    return 0


def _run_score(args: argparse.Namespace) -> int:
    """Placeholder score command."""
    raise SystemExit("`epibench score` is not implemented yet.")


def _run_plot(args: argparse.Namespace) -> int:
    """Placeholder plot command."""
    raise SystemExit("`epibench plot` is not implemented yet.")


def main(argv: list[str] | None = None) -> int:
    """Run the top-level CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        print("Choose a subcommand to run.\n")
        parser.print_help()
        return 0

    return args.handler(args)
