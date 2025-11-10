from django.apps import AppConfig


class KpiAnalyzerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kpi_analyzer'
    verbose_name = 'KPI Анализатор'

    def ready(self):
        import kpi_analyzer.signals