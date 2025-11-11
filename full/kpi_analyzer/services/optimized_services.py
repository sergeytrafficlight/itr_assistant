from concurrent.futures import ThreadPoolExecutor
import time
from django.db import connections
from django.core.cache import cache
from .kpi_analyzer import KpiPlan
from datetime import datetime, date, timedelta
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class OptimizedDBService:
    @staticmethod
    def execute_parallel_queries(filter_params):
        logger.info(f"Параллельное выполнение запросов с фильтрами: {filter_params}")
        start_time = time.time()

        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                from .db_service import DBService
                future_calls = executor.submit(DBService.get_calls_data_with_filters, filter_params)
                future_leads = executor.submit(DBService.get_leads_data_with_filters, filter_params)
                future_containers = executor.submit(DBService.get_leads_container_data_with_filters, filter_params)

                calls_data = future_calls.result()
                leads_data = future_leads.result()
                leads_container_data = future_containers.result()

            execution_time = time.time() - start_time
            logger.info(f"Параллельные запросы выполнены за {execution_time:.2f} секунд")
            return calls_data, leads_data, leads_container_data
        except Exception as e:
            logger.error(f"Ошибка в параллельных запросах: {str(e)}")
            raise


class OptimizedKPIList:
    def __init__(self, kpi_plans_data):
        logger.info(f"Инициализация OptimizedKPIList с {len(kpi_plans_data)} планами")
        start_time = time.time()

        self.plans = [KpiPlan(item) for item in kpi_plans_data]
        self._build_advanced_index()
        self._operator_kpi_cache = {}

        execution_time = time.time() - start_time
        logger.info(f"OptimizedKPIList инициализирован за {execution_time:.2f} секунд")

    def _build_advanced_index(self):
        logger.debug("Построение расширенных индексов для KPI планов")
        start_time = time.time()

        self._date_index = defaultdict(list)
        self._offer_index = defaultdict(list)
        self._affiliate_index = defaultdict(list)
        self._date_offer_index = defaultdict(lambda: defaultdict(list))

        for plan in self.plans:
            if plan.period_date:
                date_key = str(plan.period_date)
                self._date_index[date_key].append(plan)

                if plan.offer_id:
                    offer_key = str(plan.offer_id)
                    self._offer_index[offer_key].append(plan)
                    self._date_offer_index[date_key][offer_key].append(plan)

                if plan.affiliate_id:
                    aff_key = str(plan.affiliate_id)
                    self._affiliate_index[aff_key].append(plan)

        execution_time = time.time() - start_time
        logger.debug(f"Расширенные индексы построены за {execution_time:.2f}с")

    def _parse_date(self, date_str):
        if not date_str:
            return None
        try:
            if isinstance(date_str, (date, datetime)):
                return date_str.date() if isinstance(date_str, datetime) else date_str
            return datetime.strptime(str(date_str).split()[0], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    def find_kpi(self, affiliate_id, offer_id, date_str):
        start_time = time.time()

        try:
            target_date = self._parse_date(date_str)
            if not target_date:
                return None

            if offer_id and isinstance(offer_id, str) and not offer_id.isdigit():
                operator_name = offer_id.lower()
                if operator_name in self._operator_kpi_cache:
                    execution_time = time.time() - start_time
                    logger.debug(f"KPI для оператора '{operator_name}' найден в кэше за {execution_time:.3f}с")
                    return self._operator_kpi_cache[operator_name]

                fast_plan = self._find_kpi_by_operator_activity_fast(operator_name, target_date)
                if fast_plan:
                    execution_time = time.time() - start_time
                    logger.debug(f"KPI для оператора '{operator_name}' найден через активность за {execution_time:.3f}с")
                    return fast_plan

                execution_time = time.time() - start_time
                logger.warning(f"KPI для оператора '{operator_name}' не найден за {execution_time:.3f}с")
                return None

            date_key = str(target_date)

            if offer_id and str(offer_id).isdigit():
                if date_key in self._date_offer_index and str(offer_id) in self._date_offer_index[date_key]:
                    plans = self._date_offer_index[date_key][str(offer_id)]
                    if plans:
                        execution_time = time.time() - start_time
                        logger.debug(f"KPI найден по точному совпадению за {execution_time:.3f}с")
                        return plans[0]

            if offer_id and str(offer_id).isdigit():
                offer_plans = self._offer_index.get(str(offer_id), [])
                if offer_plans:
                    nearest_plan = min(
                        offer_plans,
                        key=lambda p: abs((self._parse_date(p.period_date) - target_date).days)
                        if self._parse_date(p.period_date) else float('inf')
                    )
                    execution_time = time.time() - start_time
                    logger.debug(f"KPI найден по ближайшей дате за {execution_time:.3f}с")
                    return nearest_plan

            if date_key in self._date_index and self._date_index[date_key]:
                execution_time = time.time() - start_time
                logger.debug(f"Использован общий план за дату за {execution_time:.3f}с")
                return self._date_index[date_key][0]

            execution_time = time.time() - start_time
            logger.debug(f"KPI не найден за {execution_time:.3f}с")
            return None

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Ошибка поиска KPI за {execution_time:.3f}с: {e}")
            return None

    def _find_kpi_by_operator_activity_fast(self, operator_name, target_date):
        try:
            with connections['itrade'].cursor() as cursor:
                sql = """
                    SELECT DISTINCT tl_lead.offer_id
                    FROM partners_lvlead lv
                    JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
                    JOIN partners_tllead tl_lead ON lv.tl_id = tl_lead.external_id
                    WHERE LOWER(lv_op.username) = LOWER(%s)
                    AND DATE(tl_lead.created_at) = %s
                    LIMIT 1
                """
                cursor.execute(sql, [operator_name, target_date])
                result = cursor.fetchone()

                if result and result[0]:
                    offer_id = result[0]
                    return self.find_kpi(None, offer_id, target_date)

        except Exception as e:
            logger.debug(f"Быстрый поиск KPI для оператора '{operator_name}' не удался: {e}")

        return None


class BatchOperatorProcessor:
    @staticmethod
    def get_operator_activity_bulk(operator_names, target_date):
        if not operator_names:
            return {}

        logger.info(f"Получение базовой активности для {len(operator_names)} операторов")
        start_time = time.time()

        try:
            placeholders = ','.join(['%s'] * len(operator_names))
            with connections['itrade'].cursor() as cursor:
                sql = f"""
                    SELECT 
                        lv_op.username as operator_name,
                        COUNT(*) as lead_count
                    FROM partners_lvlead lv
                    JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
                    WHERE lv_op.username IN ({placeholders})
                    AND DATE(lv.created_at) = %s
                    GROUP BY lv_op.username
                """
                params = operator_names + [target_date]
                cursor.execute(sql, params)

                result = {}
                for row in cursor.fetchall():
                    result[row[0]] = {'lead_count': row[1]}

                execution_time = time.time() - start_time
                logger.info(f"Базовая активность получена за {execution_time:.3f}с")
                return result

        except Exception as e:
            logger.error(f"Ошибка получения базовой активности: {e}")
            return {}


class QueryMonitor:
    @staticmethod
    def timed_execute(func, *args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            if execution_time > 5.0:
                logger.warning(f"МЕДЛЕННАЯ ФУНКЦИЯ {func.__name__}: {execution_time:.2f}с")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Ошибка в {func.__name__} за {execution_time:.3f}с: {e}")
            raise