"""Validate YAML configuration file input."""

import logging
from pathlib import Path
from datetime import datetime, timedelta
import yaml


logger = logging.getLogger(__name__)


def validate_config(config_path: str) -> dict:
    """Validate the configuration input"""
    config_path = Path(config_path)

    # Check if path exists
    if not config_path.exists():
        raise FileNotFoundError(f"--config-path {config_path} does not exist.")
    # Ensure file is correct type 
    if config_path.suffix.lower() not in ['.yaml', '.yml']:
        raise ValueError(f"--config-path must point to a valid .yml file. Received {config_path}")
    
    # Read in as dict, check for presence of keys
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    required_keys = {
        "hub_path", 
        "evaluation_start_date", 
        "evaluation_end_date", 
        "models", 
        "output_path"
    }
    if missing := (required_keys - set(config)):
        raise KeyError(f"Config file is missing required keys: {missing}")

    # `hub`-specific key check
    hub_path = Path(config['hub_path'])
    if (not hub_path.is_dir()) and (hub_path.exists()):
        raise NotADirectoryError(f"Config hub_path points to a file, not a directory: {hub_path}")
    if not hub_path.exists():
        raise FileNotFoundError(f"Config hub_path does nto exist: {hub_path}")
    
    # `evaluation_start_date` and `evaluation_end_date`-specific key check
    try:
        start = datetime.strptime(config['evaluation_start_date'], "%Y-%m-%d")
        end = datetime.strptime(config['evaluation_end_date'], "%Y-%m-%d")
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid date format. Dates must be valid and formatted as YYYY-MM-DD. Error: {e}"
        )
    if end < start + timedelta(days=7):
        raise ValueError(
            f"Date Range Error: End date ({config['evaluation_end_date']}) "
            f"must be at least 7 days after start date ({config['evaluation_start_date']})."
        )
    
    # `models`-specific key check
    if not isinstance(config['models'], dict) or not config['models']:
        raise ValueError("The 'models' key must be a non-empty dictionary of {'name': 'path'}.")
    for model_name, data_path in config['models'].items():
        p = Path(data_path)
        if p.suffix.lower() != '.csv':
            raise ValueError(f"Model '{model_name}' path must be a .csv file. Received: {data_path}")
        if not p.exists():
            raise FileNotFoundError(f"CSV for model '{model_name}' not found at: {data_path}")
    model_info = config['models']

    # `output_path`-specific key check
    output_path = Path(config['output_path'])
    if output_path.exists() and not output_path.is_dir():
        raise NotADirectoryError(f"Config `output_path` key must be a directory. Received {output_path}")

    logger.info("Success ✅")
    return hub_path, start, end, model_info, output_path