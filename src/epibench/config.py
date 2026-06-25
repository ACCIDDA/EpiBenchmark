"""Validate YAML configuration file input."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

from .gt_from_hub import hub_clone_setup

logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config_path: str, pipeline: str):

        valid_pipelines = ["setup", "score", "plot", "make-scorecard"]

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
        if self.pipeline == "setup":
            self.validate_setup_config()
        elif self.pipeline == "score":
            self.validate_score_config()
        elif self.pipeline == "plot":
            self.validate_plot_config()
        elif self.pipeline == "make-scorecard":
            self.validate_make_scorecard_config()

        logger.info("Success ✅")

    def _resolve_config_path(self, path_value: str | Path) -> Path:
        """
        Resolve config-provided paths.

        Relative paths are interpreted relative to the config file location.
        Absolute paths are preserved.
        """
        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    def _resolve_hub_path(self, hub_path_value: str) -> Path:
        """
        Resolve and validate a local hub path, or clone a GitHub URL.
        """
        if hub_path_value.startswith(("http://", "https://")) and "github.com" in hub_path_value:
            return hub_clone_setup(hub_url=hub_path_value)

        hub_path = self._resolve_config_path(hub_path_value)
        if not hub_path.is_dir():
            raise ValueError(
                f"`hub_path` ({hub_path_value}) either does not exist on this machine "
                "or does not point to a directory."
            )
        target_data_dir = hub_path / "target-data"
        if not target_data_dir.is_dir():
            raise ValueError("`hub_path` does not contain a required 'target-data/' directory.")
        return hub_path

    def _load_hub_reference_schedule(self, hub_path: Path) -> tuple[list[str], int | None]:
        """
        Load official reference dates and submission cutoff offset from hub metadata.

        Returns:
            - sorted reference_date values from hub-config/tasks.json, if present
            - the latest allowed submission day offset relative to reference_date
              (e.g. -3 means submission closes three days before reference_date)
        """
        tasks_path = hub_path / "hub-config" / "tasks.json"
        if not tasks_path.is_file():
            return [], None

        with open(tasks_path, "r", encoding="utf-8") as tasks_file:
            tasks_config = json.load(tasks_file)

        reference_dates = set()
        submission_cutoff_days = None

        for round_config in tasks_config.get("rounds", []):
            for model_task in round_config.get("model_tasks", []):
                task_ids = model_task.get("task_ids", {})
                reference_date_task = task_ids.get("reference_date", {})
                for field in ("required", "optional"):
                    values = reference_date_task.get(field)
                    if isinstance(values, list):
                        reference_dates.update(str(value) for value in values)

            submissions_due = round_config.get("submissions_due", {})
            if submissions_due.get("relative_to") == "reference_date":
                end_offset = submissions_due.get("end")
                if isinstance(end_offset, int):
                    submission_cutoff_days = end_offset

        return sorted(reference_dates), submission_cutoff_days

    def _infer_reference_dates_from_asof(
        self,
        hub_path: Path,
        reference_weekday: int,
    ) -> list[str]:
        """
        Infer historical reference dates by shifting available `as_of` dates to the
        hub's reference-date weekday.

        This is a fallback for hubs whose current tasks.json only describes the
        active season while older seasons are still present in target-data.
        """
        target_data_dir = hub_path / "target-data"
        parquet_path = target_data_dir / "time-series.parquet"
        csv_path = target_data_dir / "time-series.csv"

        if parquet_path.is_file():
            gt = pd.read_parquet(parquet_path, columns=["as_of"])
        elif csv_path.is_file():
            gt = pd.read_csv(csv_path, usecols=["as_of"], low_memory=False)
        else:
            return []

        if "as_of" not in gt:
            return []

        as_of_dates = pd.to_datetime(gt["as_of"], errors="coerce").dropna().dt.normalize().unique()
        inferred_reference_dates = set()
        for as_of_date in as_of_dates:
            days_until_reference = (reference_weekday - as_of_date.weekday()) % 7
            reference_date = as_of_date + pd.Timedelta(days=days_until_reference)
            inferred_reference_dates.add(reference_date.strftime("%Y-%m-%d"))

        return sorted(inferred_reference_dates)

    def _select_reference_dates_in_range(
        self,
        candidate_reference_dates: list[str],
        start_dt: datetime,
        end_dt: datetime,
        frequency_weeks: int,
    ) -> list[str]:
        """Select official reference dates that fall inside a requested span."""
        in_range_dates = [
            date_str
            for date_str in candidate_reference_dates
            if start_dt.date() <= datetime.strptime(date_str, "%Y-%m-%d").date() <= end_dt.date()
        ]
        return in_range_dates[::frequency_weeks]

    def _align_setup_dates_to_hub_schedule(
        self,
        dates_value: dict | list,
        generated_dates: list[str],
        frequency_weeks: int | None = None,
    ) -> tuple[list[str], list[str]]:
        """
        Align setup reference dates to official hub dates when metadata is available.

        Returns:
            - reference dates to expose to users and use in output paths
            - truth-data cutoff dates used for vintaged fetches
        """
        official_reference_dates, submission_cutoff_days = self._load_hub_reference_schedule(self.hub_path)
        inferred_reference_dates = []

        if official_reference_dates:
            reference_weekday = datetime.strptime(official_reference_dates[0], "%Y-%m-%d").weekday()
            inferred_reference_dates = self._infer_reference_dates_from_asof(
                hub_path=self.hub_path,
                reference_weekday=reference_weekday,
            )

        aligned_reference_dates = list(generated_dates)

        if isinstance(dates_value, dict):
            start_dt = datetime.strptime(str(dates_value["start_date"]), "%Y-%m-%d")
            end_dt = datetime.strptime(str(dates_value["end_date"]), "%Y-%m-%d")

            if official_reference_dates:
                in_range_official = self._select_reference_dates_in_range(
                    candidate_reference_dates=official_reference_dates,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    frequency_weeks=frequency_weeks or 1,
                )
                if in_range_official:
                    aligned_reference_dates = in_range_official
                elif inferred_reference_dates:
                    in_range_inferred = self._select_reference_dates_in_range(
                        candidate_reference_dates=inferred_reference_dates,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        frequency_weeks=frequency_weeks or 1,
                    )
                    if in_range_inferred:
                        aligned_reference_dates = in_range_inferred

        elif isinstance(dates_value, list):
            allowed_reference_dates = set(official_reference_dates) or set(inferred_reference_dates)
            if allowed_reference_dates:
                invalid_dates = [date for date in generated_dates if date not in allowed_reference_dates]
                if invalid_dates:
                    raise ValueError(
                        "The following setup dates are not valid hub reference dates for this hub "
                        f"schedule: {invalid_dates}. Please pass official hub reference_date values."
                    )

        if not aligned_reference_dates:
            raise ValueError(
                "No valid hub reference dates were found within the requested span. "
                "Please adjust the requested date range to overlap the hub's forecast schedule."
            )

        if submission_cutoff_days is None:
            cutoff_dates = list(aligned_reference_dates)
        else:
            cutoff_dates = [
                (
                    datetime.strptime(reference_date, "%Y-%m-%d") + timedelta(days=submission_cutoff_days)
                ).strftime("%Y-%m-%d")
                for reference_date in aligned_reference_dates
            ]

        if aligned_reference_dates != generated_dates:
            logger.info(
                "Aligned requested setup dates to hub reference dates: %s",
                aligned_reference_dates,
            )

        return aligned_reference_dates, cutoff_dates


    def validate_setup_config(self):
        """
        A method to validate a config for the `setup` pipeline.
        
        Creates attributes for each key of the config:
        - .hub_path
        - .challenge_name
        - .targets
        - .dates
        - .gt_cutoff_dates
        - .vintaging
        - .vintaging_method (None if not vintaging)
        - .output_path 
        """

        required_keys = {
        "hub_path", 
        "targets",
        "dates", 
        "vintaging", 
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        # `hub-path`-specific key check
        self.hub_path = self._resolve_hub_path(self.config["hub_path"])
        self.challenge_name = self.config.get("challenge_name")

        # `targets`-specific key check
        # ensure list, ensure not empty
        if isinstance(self.config["targets"], list):
            if len(self.config["targets"]) == 0:
                raise ValueError("`targets` key must be an unempty list.")
            else:
                targets = []
                for target in self.config["targets"]:
                    targets.append(target)
        else:
            raise ValueError(f"Please pass your `targets` key as a list of values. Received '{type(self.config['targets'])}'")
        self.targets = self.config["targets"]
        

        # `dates` -specific key check 
        dates = self.config['dates'] 
        frequency_weeks = None
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
            frequency_weeks = freq_val
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
        # if we are doing vintaging, ensure the vintaging_method is set and valid
        if (self.vintaging):
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
        else: # if we aren't doing vintaging at all, set the vintaging_method to None
            self.vintaging_method = None

        self.dates, self.gt_cutoff_dates = self._align_setup_dates_to_hub_schedule(
            dates_value=dates,
            generated_dates=self.dates,
            frequency_weeks=frequency_weeks,
        )


        # `output_path`-specific key check 
        output_path = self._resolve_config_path(self.config['output_path'])
        if output_path.exists() and not output_path.is_dir():
            raise NotADirectoryError(f"Config `output_path` key must be a directory. Received {output_path}")
        self.output_path = output_path 


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
        
        # `hub-path`-specific key check
        self.hub_path = self._resolve_hub_path(self.config["hub_path"])
        
        # `evaluation_start_date` and `evaluation_end_date`-specific key check
        # ensure they can be coerced as dates
        try:
            start = datetime.strptime(self.config['evaluation_start_date'], "%Y-%m-%d")
            end = datetime.strptime(self.config['evaluation_end_date'], "%Y-%m-%d")
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid date format. Dates must be valid and formatted as YYYY-MM-DD. Error: {e}"
            )
        # ensure neither date is in the future
        current_date = datetime.now()
        if start > current_date or end > current_date:
            raise ValueError(
                f"Date Range Error: Evaluation dates cannot be in the future. "
                f"Received:\nstart: {self.config['evaluation_start_date']}\nend: {self.config['evaluation_end_date']}."
            )
        # ensure end is at least 7 days after start
        if end < start + timedelta(days=7):
            raise ValueError(
                f"Date Range Error: End date ({self.config['evaluation_end_date']}) "
                f"must be at least 7 days AFTER start date ({self.config['evaluation_start_date']})."
            )
        self.evaluation_start_date = start
        self.evaluation_end_date = end

        # `target` key (no checks for now)
        self.target = self.config['target']

        # `baseline_model`-specific key check
        if not isinstance(self.config["baseline_model"], str):
            raise ValueError(f"`baseline_model` key must be a string/character. Received: {type(self.config['baseline_model'])}")
        self.baseline_model = self.config["baseline_model"]

        # `include_models`-specific key check
        include_models = []
        if "include_models" in self.config:
            if not isinstance(self.config['include_models'], list):
                raise ValueError(f"`include_models` key must be a list. Received: {type(self.config['include_models'])}")
            for model in self.config['include_models']:
                include_models.append(model)
            logger.info(f"Adding required baseline model {self.baseline_model} to models to process.")
            include_models.append(self.baseline_model)
            self.include_models = include_models
        else:
            logger.info(f"Adding required baseline model {self.baseline_model} to models to process.")
            include_models.append(self.baseline_model)
            self.include_models = include_models
        
        # `models`-specific key check
        if not isinstance(self.config['models'], dict) or not self.config['models']:
            raise ValueError("The 'models' key must be a non-empty dictionary of {'name': 'path'}.")
        model_info = {}
        for model_name, path in self.config['models'].items():
            data_files_list = []
            p = self._resolve_config_path(path)
            if not p.exists(): # if path doesn't exist, throw an error
                raise FileNotFoundError(f"Path specified for '{model_name}' does not exist. Path {path}")
            elif p.suffix.lower() == '.csv': # if it's just one csv path, add it 
                data_files_list.append(p)
            elif p.is_dir(): # if it's a dir path, add all csvs
                data_files_list.extend(p.glob('*.csv'))
            else: # if none, raise error
                raise ValueError(
                    f"Path specified for '{model_name}' must either point to a "
                    f"directory of .csv files, or a single .csv file. "
                    f"Received: {path}"
                )
            if len(data_files_list) < 1:
                raise ValueError(f"Found no CSV files in path(s) in config `models` key.")
            model_info[model_name] = data_files_list
        self.model_info = model_info

        
        # `output_path`-specific key check
        output_path = self._resolve_config_path(self.config['output_path'])
        if output_path.exists() and not output_path.is_dir():
            raise NotADirectoryError(f"Config `output_path` key must be a directory. Received {output_path}")
        self.output_path = output_path 

    def validate_plot_config(self):
        """
        Validate config for the `plot` pipeline.

        Will change, but currently creates attributes:
        - .score_file_path
        _ .output_path
        """
        required_keys = {"score_file_path", "output_path"}
        missing = required_keys - set(self.config)
        if missing:
            raise KeyError(f"Config file is missing required keys: {missing}")

        score_file_path = self.config["score_file_path"]

        # `score_file_path`-specific key checks
        self.score_file_path = self._resolve_config_path(score_file_path)
        if not self.score_file_path.exists():
            raise FileNotFoundError(f"Score file not found: {self.score_file_path}")
        if not self.score_file_path.is_file():
            raise ValueError(f"score_file_path must be a file. Received: {self.score_file_path}")

        # `output_path`-specific key checks
        output_path = self.config["output_path"]
        self.plot_output_dir = self._resolve_config_path(output_path)
        self.plot_output_dir.mkdir(parents=True, exist_ok=True)
        if not self.plot_output_dir.is_dir():
            raise ValueError(f"plot_output_dir must be a directory. Received: {self.plot_output_dir}")

    def validate_make_scorecard_config(self):
        """
        Validate config for the `make-scorecard` pipeline.

        Config for make-scorecard is currently undefined and will fill in later
        """
        logger.info("no config checks yet") # TODO
        logger.info("Success ✅")
