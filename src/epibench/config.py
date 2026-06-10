"""Validate YAML configuration file input."""

import logging
from pathlib import Path
from datetime import datetime, timedelta
import yaml


logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config_path: str, pipeline: str):
        if pipeline.lower() not in ['getgt', 'score']:
            raise ValueError(f"'pipeline' param must either be 'getgt' or 'score'. Received '{pipeline}'")
        self.pipeline = pipeline.lower()

        self.config_path = Path(config_path)
        # path confirmations (exists, correct type)
        if not self.config_path.exists():
            raise FileNotFoundError(f"--config-path {self.config_path} does not exist.")
        if self.config_path.suffix.lower() not in ['.yaml', '.yml']:
            raise ValueError(f"--config-path must point to a valid .yml file. Received {self.config_path}")
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        if pipeline == 'getgt':
            self.validate_getgt_config()
        elif pipeline == 'score':
            # will create attributes: TBD 
            self.validate_score_config()

        logger.info("Success ✅")


    def validate_getgt_config(self):
        """
        A method to validate a config for the `getgt` pipeline.
        
        Creates attributes for each key of the config:
        - .hub_path
        - .dates
        - .vintaging
        - .output_path 
        """

        required_keys = {
        "hub_path", 
        "dates", 
        "vintaging", 
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        # `hub_path`-specific key check
        hub_path = Path(self.config['hub_path'])
        if (not hub_path.is_dir()) and (hub_path.exists()):
            raise NotADirectoryError(f"Config `hub_path` key points to a file, not a directory: {hub_path}")
        if not hub_path.exists():
            raise FileNotFoundError(f"Config `hub_path` key does nto exist: {hub_path}")
        self.hub_path = hub_path

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


    def validate_score_config(self): # TODO
        """
        WRITE
        """
        required_keys = {
        "hub_path", 
        "evaluation_start_date", 
        "evaluation_end_date", 
        "models", 
        "output_path"
        }
        if missing := (required_keys - set(self.config)):
            raise KeyError(f"Config file is missing required keys: {missing}")
        
        # `hub_path`-specific key check
        hub_path = Path(self.config['hub_path'])
        if (not hub_path.is_dir()) and (hub_path.exists()):
            raise NotADirectoryError(f"Config `hub_path` key points to a file, not a directory: {hub_path}")
        if not hub_path.exists():
            raise FileNotFoundError(f"Config `hub_path` key does not exist: {hub_path}")
        self.hub_path = hub_path
        
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
        self.start = start
        self.end = end
        
        # `models`-specific key check
        if not isinstance(self.config['models'], dict) or not self.config['models']:
            raise ValueError("The 'models' key must be a non-empty dictionary of {'name': 'path'}.")
        for model_name, data_path in self.config['models'].items():
            p = Path(data_path)
            if p.suffix.lower() != '.csv':
                raise ValueError(f"Model '{model_name}' path must be a .csv file. Received: {data_path}")
            if not p.exists():
                raise FileNotFoundError(f"CSV for model '{model_name}' not found at: {data_path}")
        self.model_info = self.config['models']
        
        # `output_path`-specific key check
        output_path = Path(self.config['output_path'])
        if output_path.exists() and not output_path.is_dir():
            raise NotADirectoryError(f"Config `output_path` key must be a directory. Received {output_path}")
        self.output_path = output_path 
