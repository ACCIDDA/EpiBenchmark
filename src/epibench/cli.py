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
    name="list",
    short_help="List all challenges available in the EpiBenchmark library.",
    help=(
        "List every challenge bundled in the EpiBenchmark challenge library, "
        "along with its Zenodo availability status."
    ),
)
def list_challenges() -> None:
    """List the challenges available in the EpiBenchmark library."""
    from .library import print_challenge_list

    print_challenge_list()


@cli.command(
    short_help="Download a challenge's data files from Zenodo.",
    help=(
        "Download the data files for a challenge in the EpiBenchmark library "
        "from Zenodo into a local folder named after the challenge."
    ),
)
@click.argument("challenge_id", required=True)
@click.option(
    "--output-path",
    type=str,
    required=False,
    help=(
        "Directory to download the challenge into; a subfolder named after the "
        "challenge is created inside it. Defaults to the current directory."
    ),
)
def fetch(challenge_id: str, output_path: str | None) -> None:
    """Run the EpiBench fetch pipeline."""
    from .fetch import fetch as run_fetch

    run_fetch(challenge_id=challenge_id, output_path=output_path)


@cli.command(
    short_help="Score model output against ground truth.",
    help=(
        "Command to score model forecasts either from a challenge in the "
        "EpiBenchmark library or from a user-provided configuration file."
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
    "--model-name",
    type=str,
    required=False,
    help="Model name to use for the library challenge route and scorecard filtering.",
)
@click.option(
    "--output-path",
    type=str,
    required=False,
    help="Path to the directory where score outputs should be written for a library challenge.",
)
@click.option(
    "--config-path",
    type=str,
    required=False,
    help="Absolute path to your YAML configuration file.",
)
def score(
    challenge_name: str | None,
    model_data_path: str | None,
    model_name: str | None,
    output_path: str | None,
    config_path: str | None,
) -> None:
    """Run the EpiBench score pipeline."""
    from .score import score as run_score

    run_score(
        challenge_name=challenge_name,
        model_data_path=model_data_path,
        model_name=model_name,
        output_path=output_path,
        config_path=config_path,
    )


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


def main(argv: list[str] | None = None) -> int | None:
    """Run the top-level CLI."""
    return cli.main(args=argv, prog_name="epibench")
