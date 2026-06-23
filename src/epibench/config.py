"""Validate YAML configuration file input."""

import logging
from pathlib import Path
from datetime import datetime, timedelta
import yaml


logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config_path: str, pipeline: str):

        valid_pipelines = ["setup", "score", "plot"]

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

        logger.info("Validating config...")

        # Pipeline-specific validation
        if self.pipeline == "setup":
            self.validate_setup_config()
        elif self.pipeline == "score":
            self.validate_score_config()
        elif self.pipeline == "plot":
            self.validate_plot_config()

        logger.info("Success ✅")


    def validate_setup_config(self):
        """
        A method to validate a config for the `setup` pipeline.
        
        Creates attributes for each key of the config:
        - .hub
        - .dates
        - .vintaging
        - .output_path 
        """

        required_keys = {
        "hub", 
        "dates", 
        "vintaging", 
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        # `hub`-specific key check
        hub = self.config["hub"].lower()
        if not hub in ['flusight', 'flu metrocast', 'rsv', 'covid19']:
            raise ValueError(f"`hub` key must be exactly one of ['flusight', 'flu metrocast', 'rsv', 'covid19']. Received {hub}")
        else:
            self.hub = hub

        # `dates` -specific key check 
        dates = self.config['dates'] # TODO ensure dates don't span more than 1 season? not sure how past seasons will interact with our git checkout logic 
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

        # `vintaging` -specific key check
        vintaging = self.config['vintaging']
        if not isinstance(vintaging, bool):
            if not (isinstance(vintaging, str) and vintaging.lower() in ['true', 'false']):
                raise ValueError(f"Config `vintaging` key must be a boolean. Received '{vintaging}'")
        self.vintaging = vintaging if isinstance(vintaging, bool) else vintaging.lower() == 'true'

        # `output_path`-specific key check 
        output_path = Path(self.config['output_path'])
        if output_path.exists() and not output_path.is_dir():
            raise NotADirectoryError(f"Config `output_path` key must be a directory. Received {output_path}")
        self.output_path = output_path 


    def validate_score_config(self): 
        """
        A method to validate a config for the `score` pipeline.
        
        Creates attributes for each key of the config:
        - .hub
        - .evaluation_start_date
        - .evaluation_end_date
        - .target
        - .model_info
        - .output_path 
        """
        required_keys = {
        "hub", 
        "evaluation_start_date", 
        "evaluation_end_date", 
        "models", 
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        # `hub`-specific key check
        hub = self.config["hub"].lower()
        if not hub in ['flusight', 'flu metrocast', 'rsv', 'covid19']:
            raise ValueError(f"`hub` key must be exactly one of ['flusight', 'flu metrocast', 'rsv', 'covid19']. Received {hub}")
        else:
            self.hub = hub
        
        # `evaluation_start_date` and `evaluation_end_date`-specific key check
        try:
            start = datetime.strptime(self.config['evaluation_start_date'], "%Y-%m-%d")
            end = datetime.strptime(self.config['evaluation_end_date'], "%Y-%m-%d")
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid date format. Dates must be valid and formatted as YYYY-MM-DD. Error: {e}"
            )
        if end < start + timedelta(days=7):
            raise ValueError(
                f"Date Range Error: End date ({self.config['evaluation_end_date']}) "
                f"must be at least 7 days after start date ({self.config['evaluation_start_date']})."
            )
        self.evaluation_start_date = start
        self.evaluation_end_date = end

        # `target` key (no checks for now)
        self.target = self.config['target']
        
        # `models`-specific key check
        if not isinstance(self.config['models'], dict) or not self.config['models']:
            raise ValueError("The 'models' key must be a non-empty dictionary of {'name': 'path'}.")
        model_info = {}
        for model_name, path in self.config['models'].items():
            data_files_list = []
            p = Path(path)
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
        output_path = Path(self.config['output_path'])
        if output_path.exists() and not output_path.is_dir():
            raise NotADirectoryError(f"Config `output_path` key must be a directory. Received {output_path}")
        self.output_path = output_path 

    def validate_plot_config(self):
        """
        Validate config for the `plot` pipeline.

        Expected YAML structure:
          score_file_path: "EpiBenchmark_scores.csv"
          output_path: "results"
        """
        required_keys = {"score_file_path", "output_path"}
        missing = required_keys - set(self.config)
        if missing:
            raise KeyError(f"Config file is missing required keys: {missing}")

        score_file_path = self.config["score_file_path"]

        # Resolve relative to config file
        self.score_file_path = (self.base_dir / score_file_path).resolve()

        # Path must exist
        if not self.score_file_path.exists():
            raise FileNotFoundError(f"Score file not found: {self.score_file_path}")

        # Must be a file
        if not self.score_file_path.is_file():
            raise ValueError(f"score_file_path must be a file. Received: {self.score_file_path}")

        logger.info(
            f"Validated score file: {self.score_file_path}.")

        # Validate output_path
        output_path = self.config["output_path"]

        # Resolve relative to config file
        self.plot_output_dir = (self.base_dir / output_path).resolve()

        # Create directory if missing
        self.plot_output_dir.mkdir(parents=True, exist_ok=True)

        # Must be directory
        if not self.plot_output_dir.is_dir():
            raise ValueError(f"plot_output_dir must be a directory. Received: {self.plot_output_dir}")

        logger.info(
            f"Validated plot output directory: {self.plot_output_dir}")
