"""
Configuration module for JobWorkFlow MCP Server.

Provides centralized configuration management with support for:
- Environment variables
- Default values
- Path resolution
- Logging configuration
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file at project root
# config.py is in mcp-server-python/, so .env is in parent directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


def _parse_str_list(env_var: str, default: List[str]) -> List[str]:
    """Parse a comma-separated string from env into a list of strings."""
    value = os.getenv(env_var)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(env_var: str, default: bool) -> bool:
    """Parse a boolean value from an environment variable."""
    value = os.getenv(env_var)
    if value is None:
        return default
    return value.lower() in ("true", "1", "t", "y", "yes")


class Config:
    """
    Configuration class for MCP server settings.

    Supports configuration via environment variables (and .env file) with sensible defaults.
    All paths are resolved relative to the repository root.
    """

    def __init__(self):
        """Initialize configuration from environment variables and defaults."""
        # Repository root detection
        self._repo_root = self._find_repo_root()

        # Database configuration
        self.db_path = self._resolve_db_path()

        # Logging configuration
        self.log_level = os.getenv("JOBWORKFLOW_LOG_LEVEL", "INFO").upper()
        self.log_file = self._resolve_log_path()

        # Server configuration
        self.server_name = os.getenv("JOBWORKFLOW_SERVER_NAME", "jobworkflow-mcp-server")

        # Scrape tool configuration
        self.scrape_terms = _parse_str_list(
            "JOBWORKFLOW_SCRAPE_TERMS", ["ai engineer", "backend engineer", "machine learning"]
        )
        self.scrape_location = os.getenv("JOBWORKFLOW_SCRAPE_LOCATION", "Ontario, Canada")
        self.scrape_sites = _parse_str_list("JOBWORKFLOW_SCRAPE_SITES", ["linkedin"])
        self.scrape_results_wanted = int(os.getenv("JOBWORKFLOW_SCRAPE_RESULTS_WANTED", "20"))
        self.scrape_hours_old = int(os.getenv("JOBWORKFLOW_SCRAPE_HOURS_OLD", "2"))
        self.scrape_require_description = _parse_bool(
            "JOBWORKFLOW_SCRAPE_REQUIRE_DESCRIPTION", True
        )
        self.scrape_preflight_host = os.getenv(
            "JOBWORKFLOW_SCRAPE_PREFLIGHT_HOST", "www.linkedin.com"
        )
        self.scrape_retry_count = int(os.getenv("JOBWORKFLOW_SCRAPE_RETRY_COUNT", "3"))
        self.scrape_retry_sleep_seconds = float(
            os.getenv("JOBWORKFLOW_SCRAPE_RETRY_SLEEP_SECONDS", "30")
        )
        self.scrape_retry_backoff = float(os.getenv("JOBWORKFLOW_SCRAPE_RETRY_BACKOFF", "2"))
        self.scrape_save_capture_json = _parse_bool("JOBWORKFLOW_SCRAPE_SAVE_CAPTURE_JSON", True)
        self.scrape_capture_dir = os.getenv("JOBWORKFLOW_SCRAPE_CAPTURE_DIR", "data/capture")

        # bulk_read_new_jobs defaults
        self.bulk_read_limit = int(os.getenv("JOBWORKFLOW_BULK_READ_LIMIT", "50"))

        # initialize_shortlist_trackers defaults
        self.trackers_dir = os.getenv("JOBWORKFLOW_TRACKERS_DIR", "trackers")

        # career_tailor defaults
        self.full_resume_path = os.getenv(
            "JOBWORKFLOW_FULL_RESUME_PATH", "data/templates/full_resume.md"
        )
        self.resume_template_path = os.getenv(
            "JOBWORKFLOW_RESUME_TEMPLATE_PATH", "data/templates/resume_skeleton.tex"
        )
        self.applications_dir = os.getenv("JOBWORKFLOW_APPLICATIONS_DIR", "data/applications")
        self.pdflatex_cmd = os.getenv("JOBWORKFLOW_PDFLATEX_CMD", "pdflatex")

    def _find_repo_root(self) -> Path:
        """
        Find the repository root directory.

        Looks for the parent directory containing the mcp-server-python folder.

        Returns:
            Path to repository root
        """
        current_file = Path(__file__).resolve()
        # config.py is in mcp-server-python/, so parent is repo root
        return current_file.parent.parent

    def _resolve_db_path(self) -> Path:
        """
        Resolve the database path from environment or default.

        Resolution order:
        1. JOBWORKFLOW_DB environment variable (absolute or relative)
        2. JOBWORKFLOW_ROOT/data/capture/jobs.db
        3. Default: <repo_root>/data/capture/jobs.db

        Returns:
            Resolved absolute Path to database
        """
        # Check for explicit database path
        db_env = os.getenv("JOBWORKFLOW_DB")
        if db_env:
            db_path = Path(db_env)
            if db_path.is_absolute():
                return db_path
            else:
                # Relative to repo root
                return self._repo_root / db_path

        # Check for JOBWORKFLOW_ROOT
        root_env = os.getenv("JOBWORKFLOW_ROOT")
        if root_env:
            return Path(root_env) / "data" / "capture" / "jobs.db"

        # Default path relative to repo root
        return self._repo_root / "data" / "capture" / "jobs.db"

    def _resolve_log_path(self) -> Optional[Path]:
        """
        Resolve the log file path from environment.

        If JOBWORKFLOW_LOG_FILE is set, logs will be written to that file.
        Otherwise, logs go to stderr only.

        Returns:
            Path to log file, or None for stderr-only logging
        """
        log_env = os.getenv("JOBWORKFLOW_LOG_FILE")
        if not log_env:
            return None

        log_path = Path(log_env)
        if log_path.is_absolute():
            return log_path
        else:
            # Relative to repo root
            return self._repo_root / log_path

    def setup_logging(self):
        """
        Configure logging based on configuration settings.

        Sets up logging to stderr and optionally to a file.
        Log level is controlled by JOBWORKFLOW_LOG_LEVEL.
        """
        # Parse log level
        numeric_level = getattr(logging, self.log_level, logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Always add stderr handler
        stderr_handler = logging.StreamHandler()
        stderr_handler.setLevel(numeric_level)
        stderr_handler.setFormatter(formatter)
        root_logger.addHandler(stderr_handler)

        # Add file handler if log file is configured
        if self.log_file:
            # Ensure log directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            logging.info(f"Logging to file: {self.log_file}")

        logging.info(f"Log level set to: {self.log_level}")
        logging.info(f"Repository root: {self._repo_root}")
        logging.info(f"Database path: {self.db_path}")

    def get_db_path_str(self) -> str:
        """
        Get database path as string for use in tool handlers.

        Returns:
            Database path as string
        """
        return str(self.db_path)

    def validate(self) -> list[str]:
        """
        Validate configuration and return any warnings.

        Returns:
            List of warning messages (empty if all valid)
        """
        warnings = []

        # Check if database file exists
        if not self.db_path.exists():
            warnings.append(
                f"Database file not found: {self.db_path}. "
                "The server will start but tools will fail until the database is created."
            )

        # Check if log file directory is writable (if configured)
        if self.log_file:
            log_dir = self.log_file.parent
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    warnings.append(f"Cannot create log directory {log_dir}: {e}")
            elif not os.access(log_dir, os.W_OK):
                warnings.append(f"Log directory not writable: {log_dir}")

        return warnings


# Global configuration instance
config = Config()


def get_config() -> Config:
    """
    Get the global configuration instance.

    Returns:
        Global Config instance
    """
    return config
