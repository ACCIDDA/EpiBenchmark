"""Validate YAML configuration file input."""

import logging
from pathlib import Path
from datetime import datetime, timedelta
import yaml

from .gt_from_hub import hub_clone_setup

logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config_path: str, pipeline: str):

        valid_pipelines = ["setup", "score", "plot"]

        if pipeline.lower() not in valid_pipelines:
            raise ValueError(f"'pipeline' param must be one of {valid_pipelines}. Received '{pipeline}'.")
        self.pipeline = pipeline.lower()

        self.config_path = Path(config_path)

        # path confirmations (exists, correct type)
        if not self.config_path.exists():
            raise FileNotFoundError(f"--config-path {self.config_path} does not exist.")
        if self.config_path.suffix.lower() not in ['.yaml', '.yml']:
            raise ValueError(f"--config-path must point to a valid .yml file. Received {self.config_path}")
        
        # Load YAML config
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
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
        - .hub_path
        - .targets
        - .dates
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
        if self.config["hub_path"].startswith(("http://", "https://")) and "github.com" in self.config["hub_path"]: # it's a GitHub repo URL
            self.hub_path = hub_clone_setup(hub_url=self.config["hub_path"])
        else: # treat it as a Path
            hub_path = Path(self.config["hub_path"])
            if not hub_path.is_dir():
                raise ValueError(f"`hub_path` ({self.config['hub_path']}) either does not exist on this machine or does not point to a directory.")
            target_data_dir = hub_path / 'target-data'
            if not target_data_dir.is_dir():
                raise ValueError("`hub_path` does not contain a required 'target-data/' directory.")
            self.hub_path = hub_path

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


        # `output_path`-specific key check 
        output_path = Path(self.config['output_path'])
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
        if self.config["hub_path"].startswith(("http://", "https://")) and "github.com" in self.config["hub_path"]: # it's a GitHub repo URL
            self.hub_path = hub_clone_setup(hub_url=self.config["hub_path"])
        else: # treat it as a Path
            hub_path = Path(self.config["hub_path"])
            if not hub_path.is_dir():
                raise ValueError(f"`hub_path` ({self.config['hub_path']}) either does not exist on this machine or does not point to a directory.")
            target_data_dir = hub_path / 'target-data'
            if not target_data_dir.is_dir():
                raise ValueError("`hub_path` does not contain a required 'target-data/' directory.")
            self.hub_path = hub_path
        
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
        data:
          score_file_path: <path_to_csv_file>

        plot_paths:
          plot_output_dir: <path_to_save_plots>
        """
        # Validate top-level sections
        required_sections = {"data", "plot_paths"}

        missing = required_sections - set(self.config)

        if missing:
            raise KeyError(f"Missing required config sections: {missing}.")

        # Validate score_file_path
        data_config = self.config["data"]

        score_file_path = data_config.get("score_file_path")

        if not score_file_path:
            raise KeyError("Missing required key: data.score_file_path")
        
        # Creat attribute socre_file_path
        self.score_file_path = Path(score_file_path).expanduser().resolve()

        # Path must exist
        if not self.score_file_path.exists():
            raise FileNotFoundError(f"Score file not found: {self.score_file_path}")

        # Must be a file
        if not self.score_file_path.is_file():
            raise ValueError(f"score_file_path must be a file. Received: {self.score_file_path}")
        
        # Must be a CSV file
        if self.score_file_path.suffix.lower() != ".csv":
            raise ValueError(f"score_file_path must be a CSV file. Received: {self.score_file_path}.")

        logger.info(f"Validated score file: {self.score_file_path}.")

        # Validate plot_output_dir
        plot_paths_config = self.config["plot_paths"]

        plot_output_dir = plot_paths_config.get("plot_output_dir")

        if not plot_output_dir:
            raise KeyError("Missing required key: paths.plot_output_dir.")

        plot_output_dir = plot_paths_config["plot_output_dir"]

        # Create attriute plot_out_dir
        self.plot_output_dir = Path(plot_output_dir).expanduser().resolve()

        # If path exists, it must be a directory
        if self.plot_output_dir.exists() and not self.plot_output_dir.is_dir():
            raise NotADirectoryError(f"plot_output_dir must be a directory. Received: {self.plot_output_dir}.")

        logger.info(
            f"Validated plot output directory: {self.plot_output_dir}")