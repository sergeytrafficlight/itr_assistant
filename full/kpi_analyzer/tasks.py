from celery import shared_task
from django.db import connections
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task
def sync_kpi_data_from_itrade():
    """Задача для синхронизации KPI данных из внешней БД itrade на основе query_logic.txt"""
    try:
        logger.info("Starting KPI data sync from itrade")
        
        # Данные агрегируются на лету через SQL запросы, поэтому эта задача не нужна
        # Вместо этого данные будут получаться напрямую через views
        
        logger.info("KPI data sync completed - using direct SQL queries")
        
    except Exception as e:
        logger.error(f"Error in KPI data sync: {str(e)}")
        raise

@shared_task
def update_formula_dependencies():
    """Задача для обновления зависимостей формул"""
    try:
        from full.kpi_analyzer.services.formula_engine import FormulaEngine
        from .models import Cell
        
        formula_engine = FormulaEngine()
        cells_with_formulas = Cell.objects.exclude(formula='')
        
        for cell in cells_with_formulas:
            if cell.formula and cell.formula.startswith('='):
                dependencies = formula_engine.extract_dependencies(cell.formula)
                cell.dependency_list = dependencies
                cell.save()
        
        logger.info(f"Updated formula dependencies for {cells_with_formulas.count()} cells")
        
    except Exception as e:
        logger.error(f"Error updating formula dependencies: {str(e)}")
        raise

@shared_task
def refresh_kpi_data(date_from=None, date_to=None):
    """Задача для обновления KPI данных в локальной БД"""
    try:
        from .models import KpiData
        from .views import KPIAnalyticsViewSet

        if not date_from or not date_to:
            # По умолчанию за последние 30 дней
            from django.utils import timezone
            from datetime import timedelta
            date_to = timezone.now().date()
            date_from = date_to - timedelta(days=30)

        analytics_viewset = KPIAnalyticsViewSet()
        raw_data = analytics_viewset.execute_kpi_queries(
            date_from.strftime('%Y-%m-%d'),
            date_to.strftime('%Y-%m-%d'),
            None, None, None, None
        )

        # Очистка и обновление данных
        KpiData.objects.filter(date_from=date_from, date_to=date_to).delete()

        records_created = 0
        for item in raw_data:
            KpiData.objects.create(
                category=item.get('category_name'),
                offer_name=item.get('offer_name'),
                operator_name=item.get('operator_name'),
                affiliate_id=item.get('aff_id'),
                date_from=date_from,
                date_to=date_to,
                calls_count=item.get('calls_count', 0),
                leads_count=item.get('leads_count', 0),
                effective_calls=item.get('effective_calls', item.get('calls_count', 0)),
                effective_leads=item.get('effective_leads', item.get('leads_count', 0)),
                effective_rate=item.get('conversion_rate', 0),
                effective_percent=item.get('conversion_rate', 0),
            )
            records_created += 1

        logger.info(f"KPI data refreshed: {records_created} records for {date_from} to {date_to}")
        return records_created

    except Exception as e:
        logger.error(f"Error refreshing KPI data: {str(e)}")
        raise