'''
logging_config.py is used to hold methods to help with the logging module
'''

import logging.config
from logging import Logger
from os import path

import yaml

from .project_vars import LOG_NAME


def absolute_path(filename: str) -> str:
    """
    Finds the absolute path of a file based on its location
    relative to the gui module

    Parameters:
    -----------
    filename: str
        The file location based on its relative path from the gui module
    """
    abs_path = path.abspath(
        path.join(path.dirname(
            __file__), './'))
    return path.join(abs_path, filename)


def setup_logging(display_logger_name: bool = True):
    """
    Sets up logging configuration from YAML file.
    Can be safely called multiple times without creating duplicate handlers.

    Parameters:
    -----------
    display_logger_name: bool
        Whether to include logger name in the console output format
    """
    yaml_path = 'logging_config.yaml'
    abs_path = path.abspath(path.join(path.dirname(__file__), './'))
    yaml_path = path.join(abs_path, yaml_path)

    try:
        with open(yaml_path, 'r') as f:
            log_config = yaml.safe_load(f.read())

            # First, clean up existing loggers to avoid duplicates
            root = logging.getLogger()
            for handler in root.handlers[:]:
                root.removeHandler(handler)
                handler.close()

            # Define variables
            log_config['handlers']['file']['filename'] = LOG_NAME
            formatter = 'show_name' if display_logger_name else 'no_name'
            log_config['handlers']['console']['formatter'] = formatter

            logging.config.dictConfig(log_config)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error setting up logging: {e}")
        # Optionally set up a basic configuration here
        logging.basicConfig(level=logging.INFO)


def remove_logs(logger: Logger) -> None:
    """
    Removes all references to handlers for the logger and closes the logger.
    """
    if logger:
        # Make a copy since we'll modify the list
        handlers = logger.handlers.copy()
        for handler in handlers:
            logger.removeHandler(handler)
            handler.flush()
            handler.close()
