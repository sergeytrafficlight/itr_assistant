import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kpi_analyzer_project.settings')

app = Celery('kpi_analyzer_project')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Периодические задачи для KPI анализа
app.conf.beat_schedule = {
    'update-formula-dependencies-every-15-min': {
        'task': 'kpi_analyzer.tasks.update_formula_dependencies',
        'schedule': 900.0,  # Каждые 15 минут
    },
}

app.conf.timezone = 'Europe/Moscow'