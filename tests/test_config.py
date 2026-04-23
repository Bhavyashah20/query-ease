"""Tests for queryease.config"""

import pytest
from unittest.mock import patch
from queryease.config import validate_config


class TestValidateConfig:

    def test_valid_config_passes(self):
        with patch("queryease.config.GROQ_API_KEY", "gsk_test123"):
            with patch("queryease.config.DATABASE_URL", "postgresql://user:pass@localhost/db"):
                validate_config()  # should not raise

    def test_missing_groq_key_raises(self):
        with patch("queryease.config.GROQ_API_KEY", None):
            with patch("queryease.config.DATABASE_URL", "postgresql://user:pass@localhost/db"):
                with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
                    validate_config()

    def test_missing_database_url_raises(self):
        with patch("queryease.config.GROQ_API_KEY", "gsk_test123"):
            with patch("queryease.config.DATABASE_URL", None):
                with pytest.raises(EnvironmentError, match="DATABASE_URL"):
                    validate_config()

    def test_both_missing_lists_both_errors(self):
        with patch("queryease.config.GROQ_API_KEY", None):
            with patch("queryease.config.DATABASE_URL", None):
                with pytest.raises(EnvironmentError) as exc_info:
                    validate_config()
                error_msg = str(exc_info.value)
                assert "GROQ_API_KEY" in error_msg
                assert "DATABASE_URL" in error_msg
