"""
Unit Tests for App Configuration (apps.py)

Tests cover:
- AppConfig class
- Default auto field
- App name
"""

from django.test import TestCase
from recom_sys_app.apps import RecomSysConfig


class RecomSysConfigTest(TestCase):
    """Test suite for RecomSysConfig"""

    def test_config_class_exists(self):
        """Test that RecomSysConfig class exists"""
        self.assertTrue(hasattr(RecomSysConfig, "__name__"))
        self.assertEqual(RecomSysConfig.__name__, "RecomSysConfig")

    def test_default_auto_field(self):
        """Test that default_auto_field is set"""
        self.assertEqual(
            RecomSysConfig.default_auto_field, "django.db.models.BigAutoField"
        )

    def test_app_name(self):
        """Test that app name is correct"""
        self.assertEqual(RecomSysConfig.name, "recom_sys_app")

    def test_config_attributes(self):
        """Test that config has required attributes"""
        # Test class attributes directly without instantiation
        self.assertEqual(
            RecomSysConfig.default_auto_field, "django.db.models.BigAutoField"
        )
        self.assertEqual(RecomSysConfig.name, "recom_sys_app")
