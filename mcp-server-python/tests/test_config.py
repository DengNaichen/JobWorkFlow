"""
Unit tests for configuration module.

Tests configuration loading, path resolution, and validation.
"""

import os
import pytest
import logging
from pathlib import Path
from unittest.mock import patch
from config import Config


class TestConfig:
    """Test suite for Config class."""
    
    def test_default_configuration(self):
        """Test that default configuration values are set correctly."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            # Check defaults
            assert config.log_level == "INFO"
            assert config.log_file is None
            assert config.server_name == "jobworkflow-mcp-server"
            
            # Check that repo root is detected
            assert config._repo_root.exists()
            assert config._repo_root.is_dir()
    
    def test_db_path_from_env_absolute(self):
        """Test database path resolution from JOBWORKFLOW_DB (absolute)."""
        test_path = "/absolute/path/to/jobs.db"
        with patch.dict(os.environ, {"JOBWORKFLOW_DB": test_path}, clear=True):
            config = Config()
            assert str(config.db_path) == test_path
    
    def test_db_path_from_env_relative(self):
        """Test database path resolution from JOBWORKFLOW_DB (relative)."""
        with patch.dict(os.environ, {"JOBWORKFLOW_DB": "custom/jobs.db"}, clear=True):
            config = Config()
            # Should be relative to repo root
            assert config.db_path.name == "jobs.db"
            assert "custom" in str(config.db_path)
    
    def test_db_path_from_jobworkflow_root(self):
        """Test database path resolution from JOBWORKFLOW_ROOT."""
        test_root = "/opt/jobworkflow"
        with patch.dict(os.environ, {"JOBWORKFLOW_ROOT": test_root}, clear=True):
            config = Config()
            expected = Path(test_root) / "data" / "capture" / "jobs.db"
            assert config.db_path == expected
    
    def test_db_path_default(self):
        """Test default database path resolution."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            # Should be relative to repo root
            assert config.db_path.name == "jobs.db"
            assert "data" in str(config.db_path)
            assert "capture" in str(config.db_path)
    
    def test_db_path_priority(self):
        """Test that JOBWORKFLOW_DB takes priority over JOBWORKFLOW_ROOT."""
        with patch.dict(os.environ, {
            "JOBWORKFLOW_DB": "/custom/db.db",
            "JOBWORKFLOW_ROOT": "/opt/jobworkflow"
        }, clear=True):
            config = Config()
            assert str(config.db_path) == "/custom/db.db"
    
    def test_log_level_from_env(self):
        """Test log level configuration from environment."""
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_LEVEL": "DEBUG"}, clear=True):
            config = Config()
            assert config.log_level == "DEBUG"
    
    def test_log_level_case_insensitive(self):
        """Test that log level is converted to uppercase."""
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_LEVEL": "debug"}, clear=True):
            config = Config()
            assert config.log_level == "DEBUG"
    
    def test_log_file_from_env_absolute(self):
        """Test log file path from environment (absolute)."""
        test_path = "/var/log/server.log"
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_FILE": test_path}, clear=True):
            config = Config()
            assert str(config.log_file) == test_path
    
    def test_log_file_from_env_relative(self):
        """Test log file path from environment (relative)."""
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_FILE": "logs/server.log"}, clear=True):
            config = Config()
            assert config.log_file.name == "server.log"
            assert "logs" in str(config.log_file)
    
    def test_log_file_not_set(self):
        """Test that log file is None when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config.log_file is None
    
    def test_server_name_from_env(self):
        """Test server name configuration from environment."""
        with patch.dict(os.environ, {"JOBWORKFLOW_SERVER_NAME": "custom-server"}, clear=True):
            config = Config()
            assert config.server_name == "custom-server"
    
    def test_get_db_path_str(self):
        """Test getting database path as string."""
        with patch.dict(os.environ, {"JOBWORKFLOW_DB": "/test/db.db"}, clear=True):
            config = Config()
            assert config.get_db_path_str() == "/test/db.db"
            assert isinstance(config.get_db_path_str(), str)
    
    def test_validate_missing_database(self, tmp_path):
        """Test validation warns when database doesn't exist."""
        non_existent = tmp_path / "missing.db"
        with patch.dict(os.environ, {"JOBWORKFLOW_DB": str(non_existent)}, clear=True):
            config = Config()
            warnings = config.validate()
            
            assert len(warnings) > 0
            assert "Database file not found" in warnings[0]
            assert str(non_existent) in warnings[0]
    
    def test_validate_existing_database(self, tmp_path):
        """Test validation passes when database exists."""
        db_file = tmp_path / "test.db"
        db_file.touch()
        
        with patch.dict(os.environ, {"JOBWORKFLOW_DB": str(db_file)}, clear=True):
            config = Config()
            warnings = config.validate()
            
            # Should not have database warning
            db_warnings = [w for w in warnings if "Database file not found" in w]
            assert len(db_warnings) == 0
    
    def test_validate_log_directory_writable(self, tmp_path):
        """Test validation passes when log directory is writable."""
        log_file = tmp_path / "logs" / "test.log"
        
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_FILE": str(log_file)}, clear=True):
            config = Config()
            warnings = config.validate()
            
            # Should not have log directory warning
            log_warnings = [w for w in warnings if "Log directory not writable" in w]
            assert len(log_warnings) == 0
    
    def test_setup_logging_default(self):
        """Test logging setup with default configuration."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config.setup_logging()
            
            # Check root logger is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO
            
            # Should have at least one handler (stderr)
            assert len(root_logger.handlers) >= 1
    
    def test_setup_logging_with_file(self, tmp_path):
        """Test logging setup with file output."""
        log_file = tmp_path / "test.log"
        
        with patch.dict(os.environ, {
            "JOBWORKFLOW_LOG_FILE": str(log_file),
            "JOBWORKFLOW_LOG_LEVEL": "DEBUG"
        }, clear=True):
            config = Config()
            config.setup_logging()
            
            # Check root logger is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG
            
            # Should have multiple handlers (stderr + file)
            assert len(root_logger.handlers) >= 2
            
            # Log file should be created
            assert log_file.parent.exists()
    
    def test_setup_logging_creates_directory(self, tmp_path):
        """Test that logging setup creates log directory if needed."""
        log_file = tmp_path / "nested" / "logs" / "test.log"
        
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_FILE": str(log_file)}, clear=True):
            config = Config()
            config.setup_logging()
            
            # Directory should be created
            assert log_file.parent.exists()
            assert log_file.parent.is_dir()
    
    def test_setup_logging_invalid_level(self):
        """Test logging setup with invalid log level falls back to INFO."""
        with patch.dict(os.environ, {"JOBWORKFLOW_LOG_LEVEL": "INVALID"}, clear=True):
            config = Config()
            config.setup_logging()
            
            # Should fall back to INFO level
            root_logger = logging.getLogger()
            # getattr returns INFO for invalid level names
            assert root_logger.level == logging.INFO


class TestConfigIntegration:
    """Integration tests for configuration module."""
    
    def test_full_configuration_workflow(self, tmp_path):
        """Test complete configuration workflow."""
        # Set up test environment
        db_file = tmp_path / "data" / "capture" / "jobs.db"
        db_file.parent.mkdir(parents=True)
        db_file.touch()
        
        log_file = tmp_path / "logs" / "server.log"
        
        with patch.dict(os.environ, {
            "JOBWORKFLOW_DB": str(db_file),
            "JOBWORKFLOW_LOG_LEVEL": "DEBUG",
            "JOBWORKFLOW_LOG_FILE": str(log_file),
            "JOBWORKFLOW_SERVER_NAME": "test-server"
        }, clear=True):
            # Create and configure
            config = Config()
            
            # Validate
            warnings = config.validate()
            assert len(warnings) == 0
            
            # Setup logging
            config.setup_logging()
            
            # Verify configuration
            assert config.db_path == db_file
            assert config.log_level == "DEBUG"
            assert config.log_file == log_file
            assert config.server_name == "test-server"
            
            # Verify logging works
            logger = logging.getLogger("test")
            logger.info("Test message")
            
            # Log file should exist and contain message
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content
    
    def test_minimal_configuration(self):
        """Test server works with minimal configuration."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            # Should have sensible defaults
            assert config.log_level == "INFO"
            assert config.log_file is None
            assert config.server_name == "jobworkflow-mcp-server"
            
            # Should be able to setup logging
            config.setup_logging()
            
            # Should be able to get db path
            db_path = config.get_db_path_str()
            assert isinstance(db_path, str)
            assert len(db_path) > 0
