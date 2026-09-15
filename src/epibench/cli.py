"""Command-line interface for the `epibench` package."""

from __future__ import annotations

# logger enabled when tool is used via CLI
# (we don't log when functions are imported)
import logging

import click

from . import __version__

# overall `epibench`
@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="epibench")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Command-line interface for EpiBenchmark pipelines."""
    if ctx.invoked_subcommand is None:
        click.echo("Choose a subcommand to run.\n")
        click.echo(ctx.get_help())


# epibench create
@cli.command(
    name="create",
    short_help="Create model inputs on a specified cadence from hub ground truth data.",
    help="Command to get appropriately vintaged ground truth data to run your model on",
)
@click.option(
    "--config-path",
    type=str,
    required=False,
    help="Absolute path to your YAML configuration file.",
)
def create(config_path: str | None) -> None:
    """Run the EpiBenchmark create pipeline."""
    from .create import create as run_create

    run_create(config_path=config_path)


# epibench list
@cli.command(
    name="list",
    short_help="List all challenges available in the EpiBenchmark library.",
    help=(
        "List every challenge bundled in the EpiBenchmark challenge library, "
        "along with its Zenodo doi."
    ),
)
def list_challenges() -> None:
    """List the challenges available in the EpiBenchmark library."""
    from .library import print_challenge_list

    print_challenge_list()


# epibench fetch
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

    logging.basicConfig(level=logging.INFO)
    run_fetch(challenge_id=challenge_id, output_path=output_path)


# epibench score
@cli.command(
    short_help="Score model output against ground truth.",
    help=(
        "Command to score model forecasts either from a challenge in the "
        "EpiBenchmark library (strict validation), or from a user-provided configuration file."
    ),
)
@click.argument("challenge_name", required=False)
@click.option(
    "--model-data-path",
    type=str,
    required=False,
    help="Absolute path to the model data to be scored in the library challenge.",
)
@click.option(
    "--model-name",
    type=str,
    required=False,
    help="Name of the model to be scored in the library challenge.",
)
@click.option(
    "--output-path",
    type=str,
    required=False,
    help="Path to the directory where score outputs should be written for a library challenge scoring run.",
)
@click.option(
    "--config-path",
    type=str,
    required=False,
    help="Absolute path to your YAML configuration file. Sole flag to use when *not* scoring a library challenge.",
)
def score(
    challenge_name: str | None,
    model_data_path: str | None,
    model_name: str | None,
    output_path: str | None,
    config_path: str | None,
) -> None:
    """Run the EpiBenchmark score pipeline."""
    from .scoring import _score_from_config as run_score_from_config
    from .scoring import score_challenge as run_score_challenge

    logging.basicConfig(level=logging.INFO)

    using_library_challenge = challenge_name is not None or model_data_path is not None
    using_config = config_path is not None

    if using_library_challenge and using_config:
        raise click.UsageError(
            "Use either a library challenge with --model-data-path or --config-path, not both."
        )

    if using_config:
        if (
            challenge_name is not None
            or model_data_path is not None
            or model_name is not None
            or output_path is not None
        ):
            raise click.UsageError(
                "When using --config-path, do not provide challenge-name, "
                "--model-data-path, --model-name, or --output-path."
            )
        run_score_from_config(config_path=config_path)
        return

    if challenge_name is None and model_data_path is None:
        raise click.UsageError(
            "Provide either <challenge-name> with --model-data-path or --config-path."
        )
    if challenge_name is None:
        raise click.UsageError(
            "A library challenge name is required when using --model-data-path."
        )
    if model_data_path is None:
        raise click.UsageError(
            "--model-data-path is required when using a library challenge."
        )
    if model_name is None:
        raise click.UsageError(
            "--model-name is required when using a library challenge."
        )
    if output_path is None:
        raise click.UsageError(
            "--output-path is required when using a library challenge."
        )

    result = run_score_challenge(
        challenge_name=challenge_name,
        model_data_path=model_data_path,
        model_name=model_name,
    )
    result.save(output_path)


# epibench plot
@cli.command(
    short_help="Generate evaluation plots from scoring output.",
    help=(
        "Command to build plots directly from a score file, or in "
        "the context of a challenge in the EpiBenchmark library. "
        "Plotting directly from a score file will generate plots only with "
        "the models in the score file. Plotting with an EpiBenchmark challenge "
        "will include other complete models from the hub in plots."
    ),
)
@click.argument("challenge_name", required=False)
@click.option(
    "--score-file-path",
    type=str,
    required=False,
    help="Absolute path to the EpiBenchmark_scores.csv file you want to plot.",
)
@click.option(
    "--output-path",
    type=str,
    required=False,
    help="Output directory for the plot PDF. Defaults to the current directory.",
)
def plot(
    challenge_name: str | None,
    score_file_path: str | None,
    output_path: str | None,
) -> None:
    """Run the EpiBench plot pipeline."""
    logging.basicConfig(level=logging.INFO)

    if score_file_path is None:
        raise click.UsageError(
            "--score-file-path is required when running epibench plot."
        )

    from .plotting import _plot_challenge_from_score_file
    from .plotting import _plot_from_score_file

    if challenge_name is None:
        _plot_from_score_file(
            score_file_path=score_file_path,
            output_path=output_path,
        )
        return

    _plot_challenge_from_score_file(
        challenge_name=challenge_name,
        score_file_path=score_file_path,
        output_path=output_path,
    )


# main()
def main(argv: list[str] | None = None) -> int | None:
    """Run the top-level CLI."""
    return cli.main(args=argv, prog_name="epibench")
