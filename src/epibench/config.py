"""Validate YAML configuration file input."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime, time, timedelta
import logging
from pathlib import Path
from typing import Literal

import yaml

from .hub_date_utils import validate_create_dates_against_hub_rounds
from .path_utils import establish_hub_path, resolve_output_dir, resolve_path
from .table_files import TABLE_SUFFIXES, table_files

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreParameters:
    """Normalized inputs shared by YAML and programmatic scoring."""

    hub_path: Path
    evaluation_start_date: datetime
    evaluation_end_date: datetime
    target: str
    model_info: dict[str, list[Path]]
    include_models: list[str]
    baseline_model: str


@dataclass(frozen=True)
class CreateParameters:
    """Normalized inputs shared by YAML and programmatic creation."""

    hub_path: Path
    target: str
    dates: list[str]
    gt_cutoff_dates: list[str]
    ground_truth_file: str
    observed_column_name: str
    location_column_name: str
    date_column_name: str
    vintaging: bool
    vintaging_method: Literal["as_of", "checkout"] | None
    vintaging_offset: int


def _normalize_create_dates(dates: dict[str, object] | list[object]) -> list[str]:
    """Validate and expand the create pipeline's list-or-range date input."""
    if isinstance(dates, dict):
        required_date_keys = {"start_date", "end_date", "freq"}
        if missing_keys := required_date_keys.difference(dates):
            raise KeyError(
                f"The `dates` key dictionary is missing required keys {missing_keys}"
            )
        try:
            start_dt = datetime.strptime(str(dates["start_date"]), "%Y-%m-%d")
            end_dt = datetime.strptime(str(dates["end_date"]), "%Y-%m-%d")
        except (ValueError, TypeError) as error:
            raise ValueError(
                "Invalid date format in `dates` key dictionary. Dates must be "
                f"YYYY-MM-DD. Error: {error}"
            ) from error
        if start_dt > end_dt:
            raise ValueError(
                f"`start_date` ({start_dt.date()}) cannot be after "
                f"`end_date` ({end_dt.date()})."
            )

        freq_str = str(dates["freq"]).strip().lower()
        freq_parts = freq_str.split()
        if len(freq_parts) != 2:
            raise ValueError(
                f"Invalid `freq` format: '{freq_str}'. Expected format is a positive "
                "integer followed by 'week' or 'weeks' (e.g., '1 week', '2 weeks')."
            )
        try:
            frequency = int(freq_parts[0])
            if frequency <= 0:
                raise ValueError
        except ValueError as error:
            raise ValueError(
                "Frequency amount must be a positive integer. "
                f"Received: '{freq_parts[0]}'"
            ) from error
        if freq_parts[1] not in {"week", "weeks"}:
            raise ValueError(
                f"Invalid frequency unit: '{freq_parts[1]}'. Only 'week' or "
                "'weeks' are permitted for this pipeline."
            )

        normalized_dates = []
        current_date = start_dt
        while current_date <= end_dt:
            normalized_dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(weeks=frequency)
    elif isinstance(dates, list):
        normalized_dates = []
        for item in dates:
            try:
                normalized_dates.append(
                    datetime.strptime(str(item), "%Y-%m-%d").strftime("%Y-%m-%d")
                )
            except (ValueError, TypeError) as error:
                raise ValueError(
                    f"Invalid date format of date {item} in `dates` list. Dates "
                    f"must be YYYY-MM-DD. Error: {error}"
                ) from error
        normalized_dates = sorted(set(normalized_dates))
    else:
        raise ValueError(
            "Config `dates` key must either be dictionary (with keys `start_date`, "
            "`end_date`, `freq`), or a list of dates."
        )

    if not normalized_dates:
        raise ValueError("`dates` must contain at least one date.")
    latest_date = datetime.strptime(normalized_dates[-1], "%Y-%m-%d").date()
    today = datetime.today().date()
    if latest_date > today:
        raise ValueError(
            "Config `dates` key has date(s) that extend into the future. Latest "
            f"date must be on or before today: {today}"
        )
    return normalized_dates


def build_create_parameters(
    *,
    hub_path: str | Path,
    target: str,
    dates: dict[str, object] | list[object],
    ground_truth_file: str,
    observed_column_name: str,
    location_column_name: str,
    date_column_name: str,
    vintaging: bool | str,
    vintaging_method: str | None = None,
    vintaging_offset: int | None = None,
    base_dir: str | Path | None = None,
    allow_config_coercions: bool = False,
) -> CreateParameters:
    """Validate and normalize inputs used by the create workflow."""
    resolved_hub_path = establish_hub_path(hub_path, base_dir=base_dir)

    if not isinstance(target, str):
        raise ValueError(f"`target` must be a string. Received: {type(target)}")
    if not target:
        raise ValueError("`target` must be a non-empty string.")

    relative_gt_path = Path(str(ground_truth_file))
    if relative_gt_path.is_absolute() or ".." in relative_gt_path.parts:
        raise ValueError(
            "`ground_truth_file` must be a relative path contained within the hub repository."
        )
    if relative_gt_path.suffix.lower() not in {".csv", ".parquet"}:
        raise ValueError("`ground_truth_file` must point to a .csv or .parquet file.")

    column_names = {
        "observed_column_name": observed_column_name,
        "location_column_name": location_column_name,
        "date_column_name": date_column_name,
    }
    for key, value in column_names.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"`{key}` must be a non-empty string.")

    normalized_dates = _normalize_create_dates(dates)

    if isinstance(vintaging, bool):
        normalized_vintaging = vintaging
    elif (
        allow_config_coercions
        and isinstance(vintaging, str)
        and vintaging.lower() in {"true", "false"}
    ):
        normalized_vintaging = vintaging.lower() == "true"
    else:
        raise ValueError(f"Config `vintaging` key must be a boolean. Received '{vintaging}'")

    normalized_method: Literal["as_of", "checkout"] | None
    normalized_offset: int
    if normalized_vintaging:
        if vintaging_method is None:
            raise ValueError(
                "`vintaging_method` key must be included if `vintaging` is set to TRUE.\n"
                "Options are:\nvintaging_method: 'as_of'\nvintaging_method: 'checkout'"
            )
        if not isinstance(vintaging_method, str):
            raise ValueError(
                "`vintaging_method` key must be of type 'str'. "
                f"Received: {type(vintaging_method)}"
            )
        method = (
            vintaging_method.lower()
            if allow_config_coercions
            else vintaging_method
        )
        if method not in {"as_of", "checkout"}:
            raise ValueError(
                "`vintaging_method` must be one of ['as_of', 'checkout']. "
                f"Received: {vintaging_method}"
            )
        normalized_method = method

        if vintaging_offset is None:
            raise ValueError(
                "`vintaging_offset` key must be included if `vintaging` is set to TRUE. "
                "Please specify a positive integer, negative integer, or 0."
            )
        if isinstance(vintaging_offset, bool) or not isinstance(vintaging_offset, int):
            raise ValueError(
                "`vintaging_offset` must be of type 'int' (positive, negative, or 0). "
                f"Received: {type(vintaging_offset)}"
            )
        normalized_offset = vintaging_offset
    else:
        normalized_method = None
        normalized_offset = 0

    normalized_dates, cutoff_dates = validate_create_dates_against_hub_rounds(
        hub_path=resolved_hub_path,
        requested_dates=normalized_dates,
        gt_cutoff_offset=normalized_offset,
    )
    return CreateParameters(
        hub_path=resolved_hub_path,
        target=target,
        dates=normalized_dates,
        gt_cutoff_dates=cutoff_dates,
        ground_truth_file=str(relative_gt_path),
        observed_column_name=observed_column_name,
        location_column_name=location_column_name,
        date_column_name=date_column_name,
        vintaging=normalized_vintaging,
        vintaging_method=normalized_method,
        vintaging_offset=normalized_offset,
    )


def _score_date(value: str | date | datetime) -> datetime:
    """Normalize an API or YAML evaluation date to a naive datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.strptime(value, "%Y-%m-%d")


def build_score_parameters(
    *,
    hub_path: str | Path,
    evaluation_start_date: str | date | datetime,
    evaluation_end_date: str | date | datetime,
    target: str,
    models: Mapping[str, str | Path | Sequence[str | Path]],
    baseline_model: str,
    include_models: Sequence[str] | None = None,
    base_dir: str | Path | None = None,
) -> ScoreParameters:
    """Validate and normalize inputs used by the standard scoring workflow.

    ``base_dir`` is used by YAML configuration parsing so relative paths remain
    relative to the configuration file. Direct API calls omit it and resolve
    relative paths from the current working directory.
    """
    resolved_hub_path = establish_hub_path(hub_path, base_dir=base_dir)

    try:
        start = _score_date(evaluation_start_date)
        end = _score_date(evaluation_end_date)
    except (ValueError, TypeError) as error:
        raise ValueError(
            "Invalid date format. Dates must be valid and formatted as YYYY-MM-DD. "
            f"Error: {error}"
        ) from error

    current_date = datetime.now()
    if start > current_date or end > current_date:
        raise ValueError(
            "Date Range Error: Evaluation dates cannot be in the future. "
            f"Received:\nstart: {evaluation_start_date}\nend: {evaluation_end_date}."
        )
    if end < start + timedelta(days=7):
        raise ValueError(
            f"Date Range Error: End date ({evaluation_end_date}) "
            f"must be at least 7 days AFTER start date ({evaluation_start_date})."
        )

    if not isinstance(baseline_model, str):
        raise ValueError(
            "`baseline_model` key must be a string/character. "
            f"Received: {type(baseline_model)}"
        )

    if include_models is None:
        normalized_include_models = []
    elif isinstance(include_models, Sequence) and not isinstance(
        include_models, (str, bytes)
    ):
        normalized_include_models = list(include_models)
    else:
        raise ValueError(
            f"`include_models` key must be a list. Received: {type(include_models)}"
        )
    logger.info("Adding required baseline model %s to models to process.", baseline_model)
    normalized_include_models.append(baseline_model)

    if not isinstance(models, Mapping) or not models:
        raise ValueError(
            "The 'models' key must be a non-empty dictionary of {'name': 'path'}."
        )

    model_info: dict[str, list[Path]] = {}
    for model_name, model_sources in models.items():
        if isinstance(model_sources, (str, Path)):
            sources = [model_sources]
        elif isinstance(model_sources, Sequence):
            sources = list(model_sources)
        else:
            sources = [model_sources]

        data_files_list: list[Path] = []
        for source in sources:
            try:
                resolved_source = resolve_path(source, base_dir=base_dir)
            except TypeError as error:
                raise ValueError(
                    f"Path specified for '{model_name}' must be a path. Received: {source}"
                ) from error
            if not resolved_source.exists():
                raise FileNotFoundError(
                    f"Path specified for '{model_name}' does not exist. Path {source}"
                )
            if resolved_source.is_file() and resolved_source.suffix.lower() in TABLE_SUFFIXES:
                data_files_list.append(resolved_source)
            elif resolved_source.is_dir():
                data_files_list.extend(table_files(resolved_source))
            else:
                raise ValueError(
                    f"Path specified for '{model_name}' must either point to a "
                    "directory of .csv/.parquet files, or a single .csv/.parquet file. "
                    f"Received: {source}"
                )
        if not data_files_list:
            raise ValueError("Found no CSV or Parquet files in path(s) in config `models` key.")
        model_info[model_name] = data_files_list

    return ScoreParameters(
        hub_path=resolved_hub_path,
        evaluation_start_date=start,
        evaluation_end_date=end,
        target=target,
        model_info=model_info,
        include_models=normalized_include_models,
        baseline_model=baseline_model,
    )


class Config:
    def __init__(self, config_path: str, pipeline: str):

        valid_pipelines = ["create", "score"]

        if pipeline.lower() not in valid_pipelines:
            raise ValueError(f"'pipeline' param must be one of {valid_pipelines}. Received '{pipeline}'.")
        self.pipeline = pipeline.lower()

        # Validate config path
        self.config_path = Path(config_path).resolve()

        # path confirmations (exists, correct type)
        if not self.config_path.exists():
            raise FileNotFoundError(f"--config-path {self.config_path} does not exist.")
        if self.config_path.suffix.lower() not in ['.yaml', '.yml']:
            raise ValueError(f"--config-path must point to a valid .yml file. Received {self.config_path}")
        
        # Load YAML config
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Base directory
        # All relative paths will be resolved relative to the config file location.
        self.base_dir = self.config_path.parent

        # Pipeline-specific validation
        if self.pipeline == "create":
            self.validate_create_config()
        elif self.pipeline == "score":
            self.validate_score_config()
        logger.info("Success ✅")


    def validate_create_config(self):
        """
        A method to validate a config for the `create` pipeline.
        
        Creates attributes for each key of the config:
        - .hub_path
        - .challenge_name
        - .target
        - .dates
        - .gt_cutoff_dates
        - .ground_truth_file
        - .observed_column_name
        - .location_column_name
        - .date_column_name
        - .vintaging
        - .vintaging_method (None if not vintaging)
        - .vintaging_offset (None if not vintaging)
        - .output_path 
        """

        required_keys = {
            "hub_path",
            "challenge_name",
            "target",
            "ground_truth_file",
            "observed_column_name",
            "location_column_name",
            "date_column_name",
            "dates",
            "vintaging",
            "output_path",
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")

        self.create_parameters = build_create_parameters(
            hub_path=self.config["hub_path"],
            target=self.config["target"],
            dates=self.config["dates"],
            ground_truth_file=self.config["ground_truth_file"],
            observed_column_name=self.config["observed_column_name"],
            location_column_name=self.config["location_column_name"],
            date_column_name=self.config["date_column_name"],
            vintaging=self.config["vintaging"],
            vintaging_method=self.config.get("vintaging_method"),
            vintaging_offset=self.config.get("vintaging_offset"),
            base_dir=self.base_dir,
            allow_config_coercions=True,
        )
        for parameter_field in fields(self.create_parameters):
            setattr(
                self,
                parameter_field.name,
                getattr(self.create_parameters, parameter_field.name),
            )

        self.challenge_name = str(self.config["challenge_name"])
        self.output_path = resolve_output_dir(
            self.config["output_path"], base_dir=self.base_dir
        )

    def validate_score_config(self): 
        """
        A method to validate a config for the `score` pipeline.
        
        Creates attributes for each key of the config:
        - .hub_path
        - .evaluation_start_date
        - .evaluation_end_date
        - .target
        - .model_info
        - .include_models
        - .baseline_model
        - .output_path 
        """
        required_keys = {
        "hub_path", 
        "evaluation_start_date", 
        "evaluation_end_date", 
        "target",
        "models", 
        "baseline_model",
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        self.score_parameters = build_score_parameters(
            hub_path=self.config["hub_path"],
            evaluation_start_date=self.config["evaluation_start_date"],
            evaluation_end_date=self.config["evaluation_end_date"],
            target=self.config["target"],
            models=self.config["models"],
            baseline_model=self.config["baseline_model"],
            include_models=self.config.get("include_models"),
            base_dir=self.base_dir,
        )
        self.hub_path = self.score_parameters.hub_path
        self.evaluation_start_date = self.score_parameters.evaluation_start_date
        self.evaluation_end_date = self.score_parameters.evaluation_end_date
        self.target = self.score_parameters.target
        self.model_info = self.score_parameters.model_info
        self.include_models = self.score_parameters.include_models
        self.baseline_model = self.score_parameters.baseline_model
        self.output_path = resolve_path(
            self.config["output_path"],
            base_dir=self.base_dir,
        )
