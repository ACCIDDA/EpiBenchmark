"""Public Python API and shared implementation for EpiBenchmark scoring."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, Tuple, Union

import pandas as pd

from .config import Config, ScoreParameters, build_score_parameters
from .extract_model_data_details import extract_model_data_details
from .forecast_facet_helpers import pare_down_extra_models
from .load_library_challenge import load_library_challenge
from .path_utils import establish_hub_path, resolve_output_dir, resolve_path
from .quantile_validation import (
    validate_for_scoring_config_quantiles,
    validate_for_scoring_library_challenge_quantiles,
)
from .scoring_logic import score_forecasts
from .scoring_summary import (
    FILTER_SUMMARY_FILENAME,
    build_config_missing_forecast_units_summary,
    build_extra_model_facet_coverage_summary,
    format_extra_model_facet_coverage_warning,
    format_extra_model_facet_paring_summary,
    format_excluded_files_summary,
    format_missing_ground_truth_units_summary,
    format_missing_forecast_units_warning,
)
from .scorecard_functions import custom_scorecard
from .scoring_ground_truth import ScoringGroundTruth
from .table_files import TABLE_SUFFIXES, table_files

logger = logging.getLogger(__name__)

SCORES_FILENAME = "EpiBenchmark_scores.csv" # TODO, will be changed with hash, shoudl be challenge-name
SCORECARD_FILENAME = "EpiBenchmark_scorecard.csv" # TODO, will be changed with hash, should be challenge-name
FORECAST_COLUMNS_FOR_SCORING = [
    "model",
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    "target",
    "quantile_level",
    "predicted",
]


@dataclass
class ScoreResult:
    """Structured result returned by the programmatic scoring API.

    DataFrames are always available in memory. Output paths are populated after
    :meth:`save` is called. Standard scoring never produces a scorecard, so
    ``scorecard`` and ``scorecard_path`` are always ``None`` when ``mode`` is
    ``"standard"``.
    """

    mode: Literal["standard", "challenge"]
    scores: pd.DataFrame
    scorecard: Optional[pd.DataFrame] # only present if a challenge scoring run
    summary: str
    excluded_files: frozenset[str]
    output_dir: Optional[Path] = None
    scores_path: Optional[Path] = None # only populated if .save() method is used
    scorecard_path: Optional[Path] = None # only populated if .save() method is used
    summary_path: Optional[Path] = None # only populated if .save() method is used

    def save(self, output_path: str | Path | None = None) -> None:
        """Save all applicable scoring artifacts.

        - destination defaults to current working dir (unless output_path is provided)
        - director is created when it did not already exist (mkdir=T)
        - no overwrites (failure upon pre-existing file)
        """
        files_to_save = [SCORES_FILENAME, FILTER_SUMMARY_FILENAME]
        if self.scorecard is not None:
            files_to_save.append(SCORECARD_FILENAME)

        output_dir = resolve_output_dir(
            output_path or Path.cwd(),
            files_to_save=files_to_save,
        )
        scores_path = _write_output_csv("scores", self.scores, output_dir)

        scorecard_path = None
        if self.scorecard is not None:
            scorecard_path = _write_output_csv(
                "scorecard",
                self.scorecard,
                output_dir,
            )

        summary_path = output_dir / FILTER_SUMMARY_FILENAME
        summary_path.write_text(self.summary + "\n", encoding="utf-8")

        self.output_dir = output_dir
        self.scores_path = scores_path
        self.scorecard_path = scorecard_path
        self.summary_path = summary_path
        logger.info("Scoring artifacts saved to %s", output_dir)


def _write_output_csv(
    output_kind: Literal["scores", "scorecard"],
    output_data: Union[pd.DataFrame, Dict[str, object]],
    output_dir: Path,
) -> Path:
    """
    Write scores or scorecard output to disk and return the output path.
    No overwrites.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    # name for score csv
    if output_kind == "scores":
        output_path = output_dir / SCORES_FILENAME
        output_df = output_data
    # name for scorecard csv
    else:
        output_path = output_dir / SCORECARD_FILENAME
        output_df = (
            output_data
            if isinstance(output_data, pd.DataFrame)
            else pd.DataFrame([output_data])
        )
    # ensure type coercion worked
    if not isinstance(output_df, pd.DataFrame):
        raise TypeError("Score output data must be a pandas DataFrame.")

    # save
    output_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def _combine_models_for_scoring(
    model_dict: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    """Combine models using only columns consumed by the scoring pipeline."""
    standardized_models = []
    for model_name, forecast_df in model_dict.items():
        missing = set(FORECAST_COLUMNS_FOR_SCORING) - set(forecast_df.columns)
        if missing:
            raise ValueError(
                f"Model '{model_name}' is missing columns required for scoring: "
                f"{sorted(missing)}."
            )
        standardized_models.append(
            forecast_df.loc[:, FORECAST_COLUMNS_FOR_SCORING]
        )
    return pd.concat(standardized_models, ignore_index=True)


def _resolve_model_info(
    model_data_path: str | Path,
    model_name: str,
) -> Tuple[str, Dict[str, List[Path]], Path]:
    """Normalize a library-route model path into the model_info shape used by scoring."""
    resolved_model_data_path = resolve_path(model_data_path)
    # fail if it does not exist
    if not resolved_model_data_path.exists():
        raise FileNotFoundError(
            f"--model-data-path {resolved_model_data_path} does not exist."
        )
    if resolved_model_data_path.is_file():
        if resolved_model_data_path.suffix.lower() not in TABLE_SUFFIXES:
            raise ValueError(
                "--model-data-path must point to a .csv/.parquet file or a directory of those files."
            )
        model_info = {model_name: [resolved_model_data_path]}
    elif resolved_model_data_path.is_dir():
        paths = table_files(resolved_model_data_path)
        if not paths:
            raise ValueError(
                f"No CSV or Parquet files were found at --model-data-path {resolved_model_data_path}."
            )
        model_info = {model_name: paths}
    else:
        raise ValueError(
            "--model-data-path must point to a .csv/.parquet file or a directory of those files."
        )

    return model_name, model_info, resolved_model_data_path


def score(
    *,
    hub_path: str | Path,
    evaluation_start_date: str | date | datetime,
    evaluation_end_date: str | date | datetime,
    target: str,
    models: Mapping[str, pd.DataFrame],
    baseline_model: str,
    include_models: Sequence[str] | None = None,
) -> ScoreResult:
    """Run standard (non-library-challenge) scoring from explicit inputs.

    ``models`` maps each submitted model name to an in-memory Hubverse forecast
    DataFrame. The baseline and any ``include_models``
    are loaded from the hub exactly as they are for YAML-configured CLI runs.
    Results remain in memory until :meth:`ScoreResult.save` is called.
    """
    if not isinstance(models, Mapping) or not models:
        raise ValueError("`models` must be a non-empty mapping of model names to DataFrames.")
    for model_name, forecast_df in models.items():
        if not isinstance(forecast_df, pd.DataFrame):
            raise TypeError(f"`models[{model_name!r}]` must be a pandas DataFrame.")
    logger.info("Validating scoring inputs...")
    parameters = build_score_parameters(
        hub_path=hub_path,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
        target=target,
        models=models,
        baseline_model=baseline_model,
        include_models=include_models,
    )
    return _score_standard(parameters)


def _score_from_config(config_path: str | Path) -> ScoreResult:
    """Adapt a YAML score configuration to the _score_standard() functionality and automatically save it."""
    logger.info("Validating config...")
    config_object = Config(config_path=config_path, pipeline="score")
    result = _score_standard(config_object.score_parameters)
    return result.save(config_object.output_path)


def _score_standard(parameters: ScoreParameters) -> ScoreResult:
    """Execute standard scoring from normalized parameters."""

    logger.info("Validating model data...")
    excluded_files = set()  # type: Set[str]
    model_dict, locations_list = extract_model_data_details(
        hub_path=parameters.hub_path,
        model_info=parameters.model_info,
        include_models=parameters.include_models,
        eval_start_date=parameters.evaluation_start_date,
        eval_end_date=parameters.evaluation_end_date,
        target=parameters.target,
        excluded_files=excluded_files,
    )

    submitted_model_dict = {
        model_name: model_dict[model_name]
        for model_name in parameters.model_info
        if model_name in model_dict
    }

    extra_model_dict = {
        model_name: model_dict[model_name]
        for model_name in parameters.include_models
        if model_name in model_dict
    }
    extra_model_facet_coverage_summary = build_extra_model_facet_coverage_summary(
        submitted_model_dict,
        extra_model_dict,
    )
    pared_extra_model_dict, facet_paring_summaries = pare_down_extra_models(
        submitted_model_dict,
        extra_model_dict,
    )
    model_dict = {
        **submitted_model_dict,
        **pared_extra_model_dict,
    }

    logger.info("Validating quantile structure...")
    validate_for_scoring_config_quantiles(model_dict)

    missing_forecast_units_summary = build_config_missing_forecast_units_summary(
        submitted_model_dict
    )
    missing_forecast_units_warning = format_missing_forecast_units_warning(
        missing_forecast_units_summary
    )
    extra_model_facet_coverage_warning = format_extra_model_facet_coverage_warning(
        extra_model_facet_coverage_summary
    )
    extra_model_facet_paring_summary = format_extra_model_facet_paring_summary(
        facet_paring_summaries
    )
    summary_warning_blocks = "\n\n---\n\n".join(
        warning
        for warning in (
            missing_forecast_units_warning,
            extra_model_facet_paring_summary,
            extra_model_facet_coverage_warning,
        )
        if warning
    )
    global_target_end_dates = []
    if missing_forecast_units_summary is not None:
        global_target_end_dates = missing_forecast_units_summary["target_end_dates"]
    else:
        global_target_end_dates = sorted(
            {
                pd.Timestamp(target_end_date).strftime("%Y-%m-%d")
                for forecast_df in submitted_model_dict.values()
                for target_end_date in forecast_df["target_end_date"]
            }
        )

    logger.info("Retrieving and formatting ground truth data...")
    gto = ScoringGroundTruth(
        hub_path=parameters.hub_path,
        target=parameters.target,
        locations=locations_list,
        eval_start_date=parameters.evaluation_start_date,
        eval_end_date=parameters.evaluation_end_date,
    )

    df = _combine_models_for_scoring(model_dict)
    df = df.merge(gto.gt, on=["target", "target_end_date", "location"]).drop(
        columns=["target"]
    )
    missing_ground_truth_units_summary = format_missing_ground_truth_units_summary(df)

    logger.info("Scoring model data...")
    scores = score_forecasts(df, baseline_model=parameters.baseline_model)

    summary_arguments = dict(
        excluded_files=excluded_files,
        target=parameters.target,
        target_end_dates=global_target_end_dates,
        missing_forecast_units_warning=summary_warning_blocks,
        missing_ground_truth_units_summary=missing_ground_truth_units_summary,
    )
    summary = format_excluded_files_summary(**summary_arguments)
    logger.info("Process executed successfully to end 🎉.")
    return ScoreResult(
        mode="standard",
        scores=scores,
        scorecard=None,
        summary=summary,
        excluded_files=frozenset(excluded_files),
    )


def score_challenge(
    challenge_name: str,
    model_data: pd.DataFrame,
    model_name: str,
) -> ScoreResult:
    """Score a model against a bundled EpiBench library challenge.

    The complete library-challenge workflow is preserved: challenge metadata is
    loaded, model inputs and quantiles are validated, the required baseline is
    included, ground truth is merged, and both scores and the challenge-specific
    scorecard are calculated.

    ``model_data`` is an in-memory Hubverse forecast DataFrame. Results remain
    in memory until :meth:`ScoreResult.save` is called.
    """
    if not isinstance(model_data, pd.DataFrame):
        raise TypeError("`model_data` must be a pandas DataFrame.")
    return _score_challenge_with_model_info(
        challenge_name,
        {model_name: [model_data.copy()]},
        model_name,
    )


def _score_challenge_from_path(
    challenge_name: str,
    model_data_path: str | Path,
    model_name: str,
) -> ScoreResult:
    """Keep the CLI's file-based challenge scoring route."""
    _, model_info, _ = _resolve_model_info(model_data_path, model_name)
    return _score_challenge_with_model_info(challenge_name, model_info, model_name)


def _score_challenge_with_model_info(
    challenge_name: str,
    model_info: dict[str, list[Path | pd.DataFrame]],
    model_name: str,
) -> ScoreResult:
    """Score either in-memory or CLI file inputs against a library challenge."""
    logger.info("Loading challenge library...")
    challenge_definition = load_library_challenge(challenge_name)
    logger.info(f"Successfully loaded library challenge: {challenge_name} ✅")

    # set quantiles
    quantiles = challenge_definition["quantiles"]

    # set target
    target = str(challenge_definition["target"])

    # derive eval window 
    # (first ref date minus lowest horizon, last ref date plus highest horizon)
    challenge_reference_dates = challenge_definition.get("reference_dates")
    reference_date_series = pd.to_datetime(challenge_reference_dates)
    horizon_offsets = [
        pd.to_timedelta(int(horizon), unit="W")
        for horizon in challenge_definition["horizons"]
    ]
    evaluation_start_date = min(reference_date_series + min(horizon_offsets))
    evaluation_end_date = max(reference_date_series + max(horizon_offsets))

    # ensure hub clone
    hub_path = establish_hub_path(challenge_definition["hub_path"])

    # set baseline model, add to include models list
    baseline_model = challenge_definition["baseline_model"]
    include_models = [baseline_model]

    # validate input model data
    logger.info("Validating model data...")
    filtered_facets_by_file = {}  # type: Dict[str, Set[str]]
    excluded_files = set()  # type: Set[str]
    model_dict, locations_list = extract_model_data_details(
        hub_path=hub_path,
        model_info=model_info,
        include_models=include_models,
        eval_start_date=evaluation_start_date,
        eval_end_date=evaluation_end_date,
        target=target,
        required_reference_dates=challenge_reference_dates,
        required_locations=challenge_definition["locations"],
        required_horizons=challenge_definition["horizons"],
        filtered_facets_by_file=filtered_facets_by_file,
        excluded_files=excluded_files,
    )

    # validate quantiles
    logger.info("Validating quantile structure...")
    validate_for_scoring_library_challenge_quantiles(
        model_dict,
        quantiles,
        filtered_facets_by_file=filtered_facets_by_file,
    )
    summary_arguments = dict(
        excluded_files=excluded_files,
        target=target,
        reference_dates=challenge_reference_dates,
        horizons=challenge_definition["horizons"],
        quantiles=quantiles,
        locations=challenge_definition["locations"],
    )
    for model_name_key, forecast_df in model_dict.items():
        if "_source_file" in forecast_df.columns:
            model_dict[model_name_key] = forecast_df.drop(columns=["_source_file"])

    # fetch (unvintaged) gt data for scoring
    logger.info("Retrieving and formatting ground truth data...")
    gto = ScoringGroundTruth(
        hub_path=hub_path,
        target=target,
        locations=locations_list,
        eval_start_date=evaluation_start_date,
        eval_end_date=evaluation_end_date,
    )

    df = _combine_models_for_scoring(model_dict)
    df = df.merge(gto.gt, on=["target", "target_end_date", "location"]).drop(
        columns=["target"]
    )
    summary_arguments["missing_ground_truth_units_summary"] = (
        format_missing_ground_truth_units_summary(df)
    )
    summary = format_excluded_files_summary(**summary_arguments)

    # score forecasts; persistence is handled by ScoreResult.save().
    logger.info("Scoring model data...")
    scores = score_forecasts(df, baseline_model=baseline_model)

    # build the scorecard using the custom function registry
    scorecard_results = custom_scorecard(
        model_name=model_name,
        scorecard_function_names=challenge_definition["scorecard_function"],
        score_file=scores,
    )
    scorecard = pd.DataFrame([scorecard_results])

    logger.info("Process executed successfully to end 🎉.")
    return ScoreResult(
        mode="challenge",
        scores=scores,
        scorecard=scorecard,
        summary=summary,
        excluded_files=frozenset(excluded_files),
    )
