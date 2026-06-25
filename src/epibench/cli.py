"""Command-line interface for the `epibench` package."""

from __future__ import annotations

import click

from . import __version__


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="epibench")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Command-line interface for EpiBench pipelines."""
    if ctx.invoked_subcommand is None:
        click.echo("Choose a subcommand to run.\n")
        click.echo(ctx.get_help())


@cli.command(
    short_help="Set up your model runs with ground truth data pulled from specified hub.",
    help="Command to get appropriately vintaged ground truth data to run your model on",
)
@click.option(
    "--config-path",
    type=str,
    required=False,
    help="Absolute path to your YAML configuration file.",
)
def setup(config_path: str | None) -> None:
    """Run the EpiBench setup pipeline."""
    from .setup import setup as run_setup

    run_setup(config_path=config_path)


@cli.command(
    short_help="Score model output against ground truth.",
    help="Command to score (WIS) model forecasts against ground truth data.",
)
@click.option(
    "--config-path",
    type=str,
    required=False,
    help="Absolute path to your YAML configuration file.",
)
def score(config_path: str | None) -> None:
    """Run the EpiBench score pipeline."""
    from .score import score as run_score

    run_score(config_path=config_path)


@cli.command(
    short_help="Generate evaluation plots from scoring output.",
    help="Command to build plots used for evaluation of model forecast data.",
)
@click.option(
    "--config-path",
    type=str,
    default="plot-config.yml",
    required=False,
    help="Absolute path to your YAML configuration file.",
)
def plot(config_path: str | None) -> None:
    """Run the EpiBench plot pipeline."""
    from .plot import plot as run_plot

    run_plot(config_path=config_path)


@cli.command(
    name="make-scorecard",
    short_help="Generate a scorecard from a library challenge or config file.",
    help=(
        "Command to build a scorecard either from an EpiBenchmark library challenge "
        "or from a user-provided configuration file."
    ),
)
@click.argument("challenge_name", required=False)
@click.option(
    "--model-data-path",
    type=str,
    required=False,
    help="Absolute path to the model data to process with a library challenge.",
)
@click.option(
    "--config-path",
    type=str,
    required=False,
    help="Absolute path to a configuration file for custom scorecard generation.",
)
def make_scorecard(
    challenge_name: str | None,
    model_data_path: str | None,
    config_path: str | None,
) -> None:
    """Run the EpiBench make-scorecard pipeline."""
    from .make_scorecard import make_scorecard as run_make_scorecard

    run_make_scorecard(
        challenge_name=challenge_name,
        model_data_path=model_data_path,
        config_path=config_path,
    )


def main(argv: list[str] | None = None) -> int | None:
    """Run the top-level CLI."""
    return cli.main(args=argv, prog_name="epibench")
