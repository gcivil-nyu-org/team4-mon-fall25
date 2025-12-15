from django.apps import AppConfig


class RecomSysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recom_sys_app"

    def ready(self):
        """Import signals when app is ready."""
        import recom_sys_app.signals  # noqa: F401
