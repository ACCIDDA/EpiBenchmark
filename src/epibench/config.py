"""Validate YAML configuration file input."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
from pathlib import Path

import yaml

from .hub_date_utils import validate_create_dates_against_hub_rounds
from .path_utils import establish_hub_path, resolve_output_dir, resolve_path

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
            if resolved_source.suffix.lower() == ".csv":
                data_files_list.append(resolved_source)
            elif resolved_source.is_dir():
                data_files_list.extend(resolved_source.glob("*.csv"))
            else:
                raise ValueError(
                    f"Path specified for '{model_name}' must either point to a "
                    "directory of .csv files, or a single .csv file. "
                    f"Received: {source}"
                )
        if not data_files_list:
            raise ValueError("Found no CSV files in path(s) in config `models` key.")
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
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        # `hub-path`-specific key check
        self.hub_path = establish_hub_path(self.config["hub_path"], base_dir=self.base_dir)
        self.challenge_name = self.config.get("challenge_name")

        #`challenge_name`-specific key check (no checks right now)
        # ensure it is a str
        self.challenge_name = str(self.config["challenge_name"])

        # `target`-specific key check
        if not isinstance(self.config["target"], str):
            raise ValueError(
                f"`target` must be a string. Received: {type(self.config['target'])}"
            )
        if not self.config["target"]:
            raise ValueError("`target` must be a non-empty string.")
        self.target = self.config["target"]
        
        # `ground_truth_file`-specific key check
        ground_truth_file = Path(str(self.config["ground_truth_file"]))
        if ground_truth_file.is_absolute() or ".." in ground_truth_file.parts:
            raise ValueError(
                "`ground_truth_file` must be a relative path contained within the hub repository."
            )
        if ground_truth_file.suffix.lower() not in {".csv", ".parquet"}:
            raise ValueError("`ground_truth_file` must point to a .csv or .parquet file.")
        self.ground_truth_file = str(ground_truth_file)

        for key in (
            "observed_column_name",
            "location_column_name",
            "date_column_name",
        ):
            value = self.config[key]
            if not isinstance(value, str) or not value:
                raise ValueError(f"`{key}` must be a non-empty string.")
            setattr(self, key, value)

        # `dates` -specific key check 
        dates = self.config['dates'] 
        if isinstance(dates, dict):
            # check for all keys
            required_date_keys = {"start_date", "end_date", "freq"}
            if missing_keys := (required_date_keys - set(dates)):
                raise KeyError(f"The `dates` key dictionary is missing required keys {missing_keys}")
            # check date formats
            try:
                start_dt = datetime.strptime(str(dates['start_date']), "%Y-%m-%d")
                end_dt = datetime.strptime(str(dates['end_date']), "%Y-%m-%d")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid date format in `dates` key dictionary. Dates must be YYYY-MM-DD. Error: {e}")
            if start_dt > end_dt:
                raise ValueError(f"`start_date` ({start_dt.date()}) cannot be after `end_date` ({end_dt.date()}).")
            # freq key checks
            freq_str = str(dates['freq']).strip().lower()
            freq_parts = freq_str.split()
            if len(freq_parts) != 2:
                raise ValueError(
                    f"Invalid `freq` format: '{freq_str}'. "
                    "Expected format is a positive integer followed by 'week' or 'weeks' (e.g., '1 week', '2 weeks')."
                )
            try:
                freq_val = int(freq_parts[0])
                if freq_val <= 0:
                    raise ValueError
            except ValueError:
                raise ValueError(f"Frequency amount must be a positive integer. Received: '{freq_parts[0]}'")
            freq_unit = freq_parts[1]
            if freq_unit not in ["week", "weeks"]:
                raise ValueError(
                    f"Invalid frequency unit: '{freq_unit}'. "
                    "Only 'week' or 'weeks' are permitted for this pipeline."
                )
            delta = timedelta(weeks=freq_val)
            self.dates = []
            curr_dt = start_dt
            while curr_dt <= end_dt:
                self.dates.append(curr_dt.strftime("%Y-%m-%d"))
                curr_dt += delta

        elif isinstance(dates, list):
            dates_list = []
            for item in dates:
                try:
                    valid_date = datetime.strptime(str(item), "%Y-%m-%d").strftime("%Y-%m-%d")
                    dates_list.append(valid_date)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid date format of date {item} in `dates` list. Dates must be YYYY-MM-DD. Error: {e}")
            self.dates = sorted(list(set(dates_list)))

        else:
            raise ValueError(
                f"Config `dates` key must either be dictionary (with keys `start_date`, `end_date`, `freq`), "
                f"or a list of dates."
            )
        # ensure dates don't extend into the future
        latest_date_obj = datetime.strptime(self.dates[-1], "%Y-%m-%d").date() 
        today = datetime.today().date()
        if latest_date_obj > today:
            raise ValueError(f"Config `dates` key has date(s) that extend into the future. Latest date must be on or before today: {today}")

        # `vintaging` -specific key check, with `vintaging_method`
        vintaging = self.config['vintaging']
        if not isinstance(vintaging, bool):
            if not (isinstance(vintaging, str) and vintaging.lower() in ['true', 'false']):
                raise ValueError(f"Config `vintaging` key must be a boolean. Received '{vintaging}'")
        self.vintaging = vintaging if isinstance(vintaging, bool) else vintaging.lower() == 'true'
        # if we are doing vintaging, ensure the vintaging_method and vintaging_offset are set and valid
        if (self.vintaging):
            # vintaging_method
            if 'vintaging_method' not in self.config:
                raise ValueError(
                    "`vintaging_method` key must be included if `vintaging` is set to TRUE.\n"
                    "Options are:\nvintaging_method: 'as_of'\nvintaging_method: 'checkout'"
                )
            else:
                if not isinstance(self.config["vintaging_method"], str):
                    raise ValueError(f"`vintaging_method` key must be of type 'str'. Received: {type(self.config['vintaging_method'])}")
                if not self.config["vintaging_method"].lower() in ["as_of", "checkout"]:
                    raise ValueError(f"`vintaging_method` must be one of ['as_of', 'checkout']. Received: {self.config['vintaging_method']}")
            self.vintaging_method = self.config["vintaging_method"]
            # vintaging_offset
            if 'vintaging_offset' not in self.config:
                raise ValueError(
                    "`vintaging_offset` key must be included if `vintaging` is set to TRUE. "
                    "Please specify a positive integer, negative integer, or 0."
                )
            else:
                if isinstance(self.config["vintaging_offset"], bool) or not isinstance(self.config["vintaging_offset"], int):
                    raise ValueError(
                        f"`vintaging_offset` must be of type 'int' (positive, negative, or 0). "
                        f"Received: {type(self.config['vintaging_offset'])}"
                    )
            self.vintaging_offset = self.config["vintaging_offset"]
        else: # if we aren't doing vintaging at all, set the appropriate values
            self.vintaging_method = None
            self.vintaging_offset = 0 # no vintaging offset for non-vintaged runs (use the date itself)

        self.dates, self.gt_cutoff_dates = (
            validate_create_dates_against_hub_rounds(
                hub_path=self.hub_path,
                requested_dates=self.dates,
                gt_cutoff_offset=self.vintaging_offset,
            )
        )

        # `output_path`-specific key check 
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
