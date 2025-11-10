import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Q, Sum, Avg, Count
from django.db import connections
from django_filters.rest_framework import DjangoFilterBackend
import json
from rest_framework.pagination import PageNumberPagination
from datetime import datetime

from .services.output_formatter import KPIOutputFormatter
from .services.compatibility import GoogleScriptCompatibility
from .services.db_service import DBService
from .services.optimized_services import OptimizedDBService, BatchOperatorProcessor, QueryMonitor
from .services.kpi_analyzer import Grouper, Warnings
from .models import (
    Spreadsheet, Sheet, Cell, Formula, PivotTable,
    Category, Offer, Operator, Affiliate, KpiData
)

from .serializers import (
    SpreadsheetSerializer, SheetSerializer, CellSerializer,
    FormulaSerializer, PivotTableSerializer,
    CategorySerializer, OfferSerializer, OperatorSerializer,
    AffiliateSerializer, KpiDataSerializer
)
from .formula_engine import FormulaEngine
from .pivot_engine import PivotEngine

from .services.statistics import safe_div, CallEfficiencyStat, LeadContainerStat
from .services.recommendation_engine import RecommendationEngine, Recommendation
from .services.kpi_analyzer import CommonItem, CategoryItem, OptimizedKPIList, KpiPlan
from .services.optimized_services import (
    OptimizedDBService,
    BatchOperatorProcessor,
    QueryMonitor
)

logger = logging.getLogger(__name__)


class LargeResultsSetPagination(PageNumberPagination):
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = 10000


class LegacyFilterProcessor:
    @staticmethod
    def should_include_category(category_data, output_filter):
        if output_filter == 'Все':
            return True
        if output_filter == '--':
            return False
        has_calls = category_data.get('kpi_stat', {}).get('calls_group_effective_count', 0) > 0
        has_leads = category_data.get('kpi_stat', {}).get('leads_effective_count', 0) > 0
        has_offers = len(category_data.get('offers', [])) > 0
        return has_calls or has_leads or has_offers

    @staticmethod
    def should_include_offer(offer_data, category_data, output_filter):
        if output_filter == 'Все':
            return True
        if output_filter == '--':
            return False
        has_calls = offer_data.get('kpi_stat', {}).get('calls_group_effective_count', 0) > 0
        has_leads = offer_data.get('kpi_stat', {}).get('leads_effective_count', 0) > 0
        return has_calls or has_leads




def prepare_sql_array(values):
    if not values:
        return ""
    if isinstance(values, str):
        values = [values]
    return ",".join([f"'{str(v).strip()}'" for v in values if v])


def prepare_sql_array_array(values):
    return ",".join([f"'{str(v).strip()}'" for v in values])


class SpreadsheetViewSet(viewsets.ModelViewSet):
    queryset = Spreadsheet.objects.all().order_by('-id')
    serializer_class = SpreadsheetSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        logger.info("Запрос списка таблиц")
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"Возвращено {len(serializer.data)} таблиц")
        return Response(serializer.data)


class SheetViewSet(viewsets.ModelViewSet):
    queryset = Sheet.objects.all()
    serializer_class = SheetSerializer
    permission_classes = [AllowAny]


class CellViewSet(viewsets.ModelViewSet):
    queryset = Cell.objects.all()
    serializer_class = CellSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        cells_data = request.data.get('cells', [])
        logger.info(f"Массовое обновление {len(cells_data)} ячеек")
        try:
            with transaction.atomic():
                for cell_data in cells_data:
                    cell, created = Cell.objects.get_or_create(
                        sheet_id=cell_data['sheet'],
                        row=cell_data['row'],
                        col=cell_data['col'],
                        defaults=cell_data
                    )
                    if not created:
                        for key, value in cell_data.items():
                            setattr(cell, key, value)
                        cell.save()
            logger.info("Массовое обновление ячеек завершено успешно")
            return Response({'status': 'success'})
        except Exception as e:
            logger.error(f"Ошибка при массовом обновлении ячеек: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FormulaViewSet(viewsets.ModelViewSet):
    queryset = Formula.objects.all()
    serializer_class = FormulaSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def evaluate(self, request):
        formula = request.data.get('formula')
        sheet_data = request.data.get('sheet_data', {})
        logger.info(f"Вычисление формулы: {formula}")
        try:
            formula_engine = FormulaEngine()
            result = formula_engine.evaluate_formula(formula, sheet_data)
            dependencies = formula_engine.extract_dependencies(formula)
            logger.info(f"Формула вычислена успешно, результат: {result}")
            return Response({
                'result': result,
                'dependencies': dependencies
            })
        except Exception as e:
            logger.error(f"Ошибка вычисления формулы: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PivotTableViewSet(viewsets.ModelViewSet):
    queryset = PivotTable.objects.all()
    serializer_class = PivotTableSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        pivot_table = self.get_object()
        logger.info(f"Генерация сводной таблицы {pivot_table.id}")
        try:
            pivot_engine = PivotEngine()
            result = pivot_engine.generate_pivot(pivot_table)
            logger.info(f"Сводная таблица сгенерирована, строк: {len(result)}")
            return Response({'data': result})
        except Exception as e:
            logger.error(f"Ошибка генерации сводной таблицы: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def available_fields(self, request):
        logger.info("Запрос доступных полей для сводных таблиц")
        pivot_engine = PivotEngine()
        fields = pivot_engine.get_available_fields()
        return Response({'fields': fields})


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']


class OfferviewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'external_id']


class OperatorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['username']


class AffiliateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Affiliate.objects.all()
    serializer_class = AffiliateSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['external_id']


class KPIAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def get_filter_params(self, request):
        params = {
            'date_from': self.normalize_datetime(request.query_params.get('date_from'), "00:00:00"),
            'date_to': self.normalize_datetime(request.query_params.get('date_to'), "23:59:59"),
            'group_rows': request.query_params.get('group_rows', 'Нет'),
            'advertiser': request.query_params.get('advertiser', '').lower(),
            'output': request.query_params.get('output', 'Все'),
            'aff_id': request.query_params.get('aff_id', ''),
            'category': request.query_params.get('category', '').lower(),
            'offer_id': request.query_params.get('offer_id', ''),
            'operator_name': request.query_params.get('operator_name', '').lower(),
        }
        logger.debug(f"Параметры фильтрации: {params}")
        return params

    def normalize_datetime(self, datetime_str, time_part="00:00:00"):
        if not datetime_str:
            return ""
        try:
            if " " in datetime_str:
                return datetime_str
            else:
                return f"{datetime_str} {time_part}"
        except Exception:
            return datetime_str

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        filter_params = self.get_filter_params(request)
        date_from = filter_params['date_from']
        date_to = filter_params['date_to']
        if not date_from or not date_to:
            logger.warning("Отсутствуют обязательные параметры date_from и date_to")
            return Response({'error': 'date_from и date_to обязательны'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Аналитика KPI за период {date_from} - {date_to}")
        try:
            results = self.execute_kpi_queries_with_filters(filter_params)
            summary = self.calculate_summary(results)
            logger.info(f"Аналитика завершена, записей: {len(results)}, сводка: {summary}")
            return Response({
                'data': results,
                'summary': summary,
                'period': f"{date_from} - {date_to}",
                'filters_applied': filter_params
            })
        except Exception as e:
            logger.error(f"Ошибка при аналитике KPI: {str(e)}")
            return Response({'error': f'Ошибка базы: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def execute_kpi_queries_with_filters(self, filter_params):
        logger.debug(f"Выполнение KPI запросов с фильтрами: {filter_params}")
        return QueryMonitor.timed_execute(OptimizedDBService.execute_parallel_queries, filter_params)

    def get_calls_data_with_filters(self, filters):
        logger.debug(f"Получение данных звонков с фильтрами: {filters}")
        try:
            connection = connections['itrade']
            with connection.cursor() as cursor:
                sql = """
                    SELECT COALESCE(group_offer.name, 'Без категории') as category_name,
                           COALESCE(po.id, 0) as offer_id,
                           COALESCE(po.name, 'Без оффера') as offer_name,
                           COALESCE(lv_op.username, 'Без оператора') as operator_name,
                           COALESCE(pt.webmaster_id, 0) as aff_id,
                           COUNT(*) as calls_count,
                           SUM(partners_atscallevent.billsec) as total_duration
                    FROM partners_atscallevent
                    LEFT JOIN partners_lvoperator lv_op ON lv_op.id = partners_atscallevent.lvoperator_id
                    LEFT JOIN partners_lvlead ON partners_atscallevent.lvlead_id = partners_lvlead.id
                    LEFT JOIN partners_tllead pt ON partners_lvlead.tl_id = pt.external_id
                    LEFT JOIN partners_offer po ON pt.offer_id = po.id
                    LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = po.id
                    LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
                    LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
                    WHERE partners_atscallevent.billsec >= 30
                      AND DATE_ADD(partners_atscallevent.calldate, INTERVAL 3 HOUR) BETWEEN %s AND %s
                      AND (group_offer.name NOT IN ('Архив', 'Входящая линия') OR group_offer.name IS NULL)
                """
                params = [filters['date_from'], filters['date_to']]
                if filters.get('category'):
                    sql += " AND group_offer.name = %s"
                    params.append(filters['category'])
                if filters.get('offer_id'):
                    sql += " AND po.id = %s"
                    params.append(filters['offer_id'])
                if filters.get('operator_name'):
                    sql += " AND LOWER(lv_op.username) = %s"
                    params.append(filters['operator_name'])
                if filters.get('aff_id'):
                    sql += " AND pt.webmaster_id = %s"
                    params.append(filters['aff_id'])
                if filters.get('advertiser'):
                    sql += " AND LOWER(subsystem.name) = %s"
                    params.append(filters['advertiser'])
                sql += " GROUP BY category_name, offer_id, offer_name, operator_name, aff_id"

                cursor.execute(sql, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.debug(f"Получено {len(results)} записей звонков")
                return results
        except Exception as e:
            logger.error(f"Ошибка при получении данных звонков: {str(e)}")
            raise

    def get_leads_data_with_filters(self, filters):
        logger.debug(f"Получение данных лидов с фильтрами: {filters}")
        try:
            connection = connections['itrade']
            with connection.cursor() as cursor:
                sql = """
                    SELECT COALESCE(group_offer.name, 'Без категории') as category_name,
                           COALESCE(offer.id, 0) as offer_id,
                           COALESCE(offer.name, 'Без оффера') as offer_name,
                           COALESCE(lv_op.username, 'Без оператора') as operator_name,
                           COALESCE(tl_lead.webmaster_id, 0) as aff_id,
                           COUNT(*) as leads_count
                    FROM partners_lvlead lv
                    LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
                    LEFT JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
                    LEFT JOIN partners_tllead tl_lead ON lv.tl_id = tl_lead.external_id
                    LEFT JOIN partners_offer offer ON tl_lead.offer_id = offer.id
                    LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
                    LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
                    LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = tl_lead.subsystem_id
                    WHERE DATE_ADD(lv.approved_at, INTERVAL 3 HOUR) BETWEEN %s AND %s
                      AND (group_offer.name NOT IN ('Архив', 'Входящая линия') OR group_offer.name IS NULL)
                """
                params = [filters['date_from'], filters['date_to']]
                if filters.get('category'):
                    sql += " AND group_offer.name = %s"
                    params.append(filters['category'])
                if filters.get('offer_id'):
                    sql += " AND offer.id = %s"
                    params.append(filters['offer_id'])
                if filters.get('operator_name'):
                    sql += " AND LOWER(lv_op.username) = %s"
                    params.append(filters['operator_name'])
                if filters.get('aff_id'):
                    sql += " AND tl_lead.webmaster_id = %s"
                    params.append(filters['aff_id'])
                if filters.get('advertiser'):
                    sql += " AND LOWER(subsystem.name) = %s"
                    params.append(filters['advertiser'])
                sql += " GROUP BY category_name, offer_id, offer_name, operator_name, aff_id"

                cursor.execute(sql, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.debug(f"Получено {len(results)} записей лидов")
                return results
        except Exception as e:
            logger.error(f"Ошибка при получении данных лидов: {str(e)}")
            raise

    def get_leads_container_data_with_filters(self, filters):
        logger.debug(f"Получение данных контейнера лидов с фильтрами: {filters}")
        try:
            connection = connections['itrade']
            with connection.cursor() as cursor:
                sql = """
                    SELECT COALESCE(group_offer.name, 'Без категории') as category_name,
                           COALESCE(offer.id, 0) as offer_id,
                           COALESCE(pt.webmaster_id, 0) as aff_id,
                           COUNT(CASE WHEN lv.buyout_at IS NOT NULL THEN 1 END) as buyout_count,
                           COUNT(*) as total_leads
                    FROM partners_lvlead lv
                    LEFT JOIN partners_tllead pt ON lv.tl_id = pt.external_id
                    LEFT JOIN partners_offer offer ON pt.offer_id = offer.id
                    LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
                    LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
                    LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
                    WHERE DATE_ADD(lv.created_at, INTERVAL 3 HOUR) BETWEEN %s AND %s
                      AND (group_offer.name NOT IN ('Архив', 'Входящая линия') OR group_offer.name IS NULL)
                """
                params = [filters['date_from'], filters['date_to']]
                if filters.get('category'):
                    sql += " AND group_offer.name = %s"
                    params.append(filters['category'])
                if filters.get('offer_id'):
                    sql += " AND offer.id = %s"
                    params.append(filters['offer_id'])
                if filters.get('aff_id'):
                    sql += " AND pt.webmaster_id = %s"
                    params.append(filters['aff_id'])
                if filters.get('advertiser'):
                    sql += " AND LOWER(subsystem.name) = %s"
                    params.append(filters['advertiser'])
                sql += " GROUP BY category_name, offer_id, aff_id"

                cursor.execute(sql, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.debug(f"Получено {len(results)} записей контейнера лидов")
                return results
        except Exception as e:
            logger.error(f"Ошибка при получении данных контейнера лидов: {str(e)}")
            raise

    def aggregate_kpi_data(self, calls_data, leads_data, leads_container_data):
        logger.debug(
            f"Агрегация KPI данных: звонки={len(calls_data)}, лиды={len(leads_data)}, контейнер={len(leads_container_data)}")
        aggregated = {}
        for call in calls_data:
            key = f"{call['category_name']}_{call['offer_id']}_{call['operator_name']}_{call['aff_id']}"
            if key not in aggregated:
                aggregated[key] = {
                    'category_name': call['category_name'],
                    'offer_id': call['offer_id'],
                    'offer_name': call['offer_name'],
                    'operator_name': call['operator_name'],
                    'aff_id': call['aff_id'],
                    'calls_count': 0,
                    'total_duration': 0,
                    'leads_count': 0,
                    'buyout_count': 0,
                    'total_container_leads': 0
                }
            aggregated[key]['calls_count'] += call['calls_count']
            aggregated[key]['total_duration'] += call['total_duration']

        for lead in leads_data:
            key = f"{lead['category_name']}_{lead['offer_id']}_{lead['operator_name']}_{lead['aff_id']}"
            if key not in aggregated:
                aggregated[key] = {
                    'category_name': lead['category_name'],
                    'offer_id': lead['offer_id'],
                    'offer_name': lead['offer_name'],
                    'operator_name': lead['operator_name'],
                    'aff_id': lead['aff_id'],
                    'calls_count': 0,
                    'total_duration': 0,
                    'leads_count': 0,
                    'buyout_count': 0,
                    'total_container_leads': 0
                }
            aggregated[key]['leads_count'] = lead['leads_count']

        for container in leads_container_data:
            key = f"{container['category_name']}_{container['offer_id']}_all_{container['aff_id']}"
            if key in aggregated:
                aggregated[key]['buyout_count'] = container['buyout_count']
                aggregated[key]['total_container_leads'] = container['total_leads']

        for item in aggregated.values():
            item['conversion_rate'] = round((item['leads_count'] / item['calls_count'] * 100), 2) if item['calls_count'] > 0 else 0
            item['avg_call_duration'] = round(item['total_duration'] / item['calls_count'], 1) if item['calls_count'] > 0 else 0
            item['buyout_rate'] = round((item['buyout_count'] / item['leads_count'] * 100), 2) if item['leads_count'] > 0 else 0

        logger.debug(f"Агрегация завершена, итого записей: {len(aggregated.values())}")
        return list(aggregated.values())

    def calculate_summary(self, data):
        if not data:
            logger.debug("Нет данных для расчета сводки")
            return {}
        total_calls = sum(item.get('calls_count', 0) for item in data)
        total_leads = sum(item.get('leads_count', 0) for item in data)
        total_buyouts = sum(item.get('buyout_count', 0) for item in data)
        summary = {
            'total_calls': total_calls,
            'total_leads': total_leads,
            'total_buyouts': total_buyouts,
            'conversion_rate': round((total_leads / total_calls * 100), 2) if total_calls else 0,
            'buyout_rate': round((total_buyouts / total_leads * 100), 2) if total_leads else 0,
            'records_count': len(data)
        }
        logger.debug(f"Рассчитана сводка: {summary}")
        return summary

    @action(detail=False, methods=['get'])
    def offers_list(self, request):
        logger.info("Запрос списка офферов")
        try:
            v = {
                'category': request.query_params.get('category'),
                'offer_id': request.query_params.get('offer_id')
            }
            results = DBService.get_offers(v)
            logger.info(f"Возвращено {len(results)} офферов")
            return Response({'offers': results})
        except Exception as e:
            logger.error(f"Ошибка при получении списка офферов: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            logger.error(f"Ошибка при получении списка офферов: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def kpi_plans_full(self, request):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if not date_from or not date_to:
            logger.warning("Отсутствуют date_from и date_to для KPI планов")
            return Response({'error': 'date_from и date_to обязательны'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Получение полных KPI планов с {date_from} по {date_to}")
        try:
            results = DBService.get_kpi_plans_data(date_from, date_to)
            logger.info(f"Получено {len(results)} KPI планов")
            return Response({'kpi_plans': results})
        except Exception as e:
            logger.error(f"Ошибка при получении KPI планов: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class KPIAdvancedAnalysisViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    pagination_class = LargeResultsSetPagination

    @action(detail=False, methods=['post'])
    def advanced_analysis(self, request):
        analysis_params = request.data.get('params', {})
        output_filter = analysis_params.get('output', 'Все')
        logger.info(f"Расширенный анализ с параметрами: {analysis_params}")

        grouper = Grouper()
        warnings = Warnings()

        try:
            stat = self.create_advanced_kpi_statistics(analysis_params)
            stat.finalyze()

            operator_names = [op.key for cat in stat.category.values() for op in cat.operator.values()]
            if operator_names:
                logger.debug(f"Получение активности для {len(operator_names)} операторов")
                BatchOperatorProcessor.get_operator_activity_bulk(operator_names, analysis_params.get('date_to'))

            raw_result = self.format_advanced_analysis_result_for_output(stat)

            filtered_result = []
            for category in raw_result:
                if LegacyFilterProcessor.should_include_category(category, output_filter):
                    filtered_offers = [
                        offer for offer in category.get('offers', [])
                        if LegacyFilterProcessor.should_include_offer(offer, category, output_filter)
                    ]
                    cat_copy = category.copy()
                    cat_copy['offers'] = filtered_offers
                    filtered_result.append(cat_copy)

            formatter = KPIOutputFormatter()
            formatted_data = formatter.create_output_structure(filtered_result)

            logger.info(f"Расширенный анализ завершен, категорий: {len(filtered_result)}")
            return Response({
                'success': True,
                'data': formatted_data,
                'warnings': warnings.get_warnings(),
                'grouping': grouper.get_structure(),
                'summary': self.calculate_advanced_summary(stat),
                'recommendations': self.extract_recommendations(stat),
                'structure_type': 'google_sheets_compatible'
            })

        except Exception as e:
            logger.error(f"Ошибка при расширенном анализе: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response({'error': f'Ошибка: {str(e)}'}, status=500)

    @action(detail=False, methods=['post'])
    def google_sheets_format(self, request):
        analysis_params = request.data.get('params', {})
        output_filter = analysis_params.get('output', 'Все')
        logger.info(f"Форматирование для Google Sheets с параметрами: {analysis_params}")

        date_from = analysis_params.get('date_from')
        date_to = analysis_params.get('date_to')
        if not date_from or not date_to:
            logger.warning("Отсутствуют date_from и date_to для Google Sheets формата")
            return Response({'error': 'date_from и date_to обязательны'}, status=400)

        try:
            stat = self.create_advanced_kpi_statistics(analysis_params)
            stat.finalyze()

            raw_result = self.format_advanced_analysis_result_for_output(stat)

            filtered_result = []
            for category in raw_result:
                if LegacyFilterProcessor.should_include_category(category, output_filter):
                    filtered_offers = [
                        offer for offer in category.get('offers', [])
                        if LegacyFilterProcessor.should_include_offer(offer, category, output_filter)
                    ]
                    cat_copy = category.copy()
                    cat_copy['offers'] = filtered_offers
                    filtered_result.append(cat_copy)

            formatter = KPIOutputFormatter()
            sheets_data = formatter.create_output_structure(filtered_result)

            logger.info(f"Данные для Google Sheets подготовлены, строк: {len(sheets_data)}")
            return Response({
                'success': True,
                'data': sheets_data,
                'metadata': {
                    'columns_count': len(sheets_data[0]) if sheets_data else 0,
                    'rows_count': len(sheets_data),
                    'format': 'google_sheets_exact',
                    'period': f"{date_from} - {date_to}"
                }
            })

        except Exception as e:
            logger.error(f"Ошибка при форматировании для Google Sheets: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response({'error': f'Ошибка: {str(e)}'}, status=500)

    @action(detail=False, methods=['post'])
    def debug_data(self, request):
        analysis_params = request.data.get('params', {})

        stat = self.create_advanced_kpi_statistics(analysis_params)
        stat.finalyze()
        raw_result = self.format_advanced_analysis_result_for_output(stat)

        return Response({
            'categories_count': len(raw_result),
            'first_category': raw_result[0] if raw_result else None,
            'all_categories_keys': [cat['key'] for cat in raw_result],
            'debug_info': f"Всего категорий: {len(raw_result)}"
        })

    def create_advanced_kpi_statistics(self, params):
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if not date_from or not date_to:
            logger.error("Отсутствуют date_from и date_to для создания статистики")
            raise ValueError("date_from и date_to обязательны")

        logger.info(f"Создание расширенной KPI статистики с {date_from} по {date_to}")

        try:
            analysis_date = datetime.strptime(date_to.split()[0], '%Y-%m-%d').date()
        except:
            analysis_date = datetime.now().date()

        logger.info(f"Дата анализа для KPI поиска: {analysis_date}")

        kpi_plans_data = DBService.get_kpi_plans_data(date_from, date_to)

        kpi_list = OptimizedKPIList(kpi_plans_data)

        analytics = KPIAnalyticsViewSet()
        calls_data = analytics.get_calls_data_with_filters(params)
        leads_data = analytics.get_leads_data_with_filters(params)
        container_data = analytics.get_leads_container_data_with_filters(params)

        class KPIStat:
            def __init__(self, kpi_list, analysis_date):
                self.category = {}
                self.kpi_list = kpi_list
                self.analysis_date = analysis_date

            def push_lead(self, sql_data):
                cat_name = sql_data.get('category_name', 'Без категории')
                if cat_name not in self.category:
                    self.category[cat_name] = CategoryItem(cat_name, cat_name, self.analysis_date)
                self.category[cat_name].push_lead({
                    'offer_id': sql_data.get('offer_id', 0),
                    'offer_name': sql_data.get('offer_name', 'Без оффера'),
                    'aff_id': sql_data.get('aff_id', 0),
                    'operator_name': sql_data.get('operator_name', 'Без оператора')
                }, sql_data)

            def push_call(self, sql_data):
                cat_name = sql_data.get('category_name', 'Без категории')
                if cat_name not in self.category:
                    self.category[cat_name] = CategoryItem(cat_name, cat_name, self.analysis_date)
                self.category[cat_name].push_call({
                    'offer_id': sql_data.get('offer_id', 0),
                    'offer_name': sql_data.get('offer_name', 'Без оффера'),
                    'aff_id': sql_data.get('aff_id', 0),
                    'operator_name': sql_data.get('operator_name', 'Без оператора')
                }, sql_data)

            def push_lead_container(self, sql_data):
                cat_name = sql_data.get('category_name', 'Без категории')
                if cat_name not in self.category:
                    self.category[cat_name] = CategoryItem(cat_name, cat_name, self.analysis_date)
                self.category[cat_name].push_lead_container({
                    'offer_id': sql_data.get('offer_id', 0),
                    'offer_name': sql_data.get('offer_name', 'Без оффера'),
                    'aff_id': sql_data.get('aff_id', 0)
                }, sql_data)

            def finalyze(self):
                for cat in self.category.values():
                    try:
                        cat.finalyze(self.kpi_list)
                    except Exception as e:
                        logger.error(f"Ошибка при финализации категории {cat.key}: {str(e)}")
                        # Продолжаем обработку других категорий даже если одна упала

        stat = KPIStat(kpi_list, analysis_date)
        for c in calls_data: stat.push_call(c)
        for l in leads_data: stat.push_lead(l)
        for lc in container_data: stat.push_lead_container(lc)
        logger.info(f"Статистика создана, категорий: {len(stat.category)}")
        stat.finalyze()
        return stat

    def format_advanced_analysis_result_for_output(self, stat):
        logger.debug("Форматирование результатов расширенного анализа")
        result = []
        for category_key, category in stat.category.items():
            category_data = {
                'type': 'category',
                'key': category.key,
                'description': category.description,
                'kpi_stat': {
                    'calls_group_effective_count': category.kpi_stat.calls_group_effective_count,
                    'leads_effective_count': category.kpi_stat.leads_effective_count,
                    'effective_percent': category.kpi_stat.effective_percent,
                    'effective_rate': category.kpi_stat.effective_rate,
                    'expecting_effective_rate': category.kpi_stat.expecting_effective_rate,
                },
                'lead_container': {
                    'leads_non_trash_count': category.lead_container.leads_non_trash_count,
                    'leads_approved_count': category.lead_container.leads_approved_count,
                    'leads_buyout_count': category.lead_container.leads_buyout_count,
                },
                'recommendations': {
                    'efficiency': {
                        'value': category.recommended_effeciency.value if category.recommended_effeciency else None,
                        'comment': category.recommended_effeciency.comment if category.recommended_effeciency else ''
                    },
                    'approve': {
                        'value': category.recommended_approve.value if category.recommended_approve else None,
                        'comment': category.recommended_approve.comment if category.recommended_approve else ''
                    },
                    'buyout': {
                        'value': category.recommended_buyout.value if category.recommended_buyout else None,
                        'comment': category.recommended_buyout.comment if category.recommended_buyout else ''
                    },
                    'confirmation_price': {
                        'value': category.recommended_confirmation_price.value if category.recommended_confirmation_price else None,
                        'comment': category.recommended_confirmation_price.comment if category.recommended_confirmation_price else ''
                    }
                },
                'approve_rate_plan': category.approve_rate_plan,
                'buyout_rate_plan': category.buyout_rate_plan,
                'approve_percent_fact': category.approve_percent_fact,
                'buyout_percent_fact': category.buyout_percent_fact,
                'offers': [],
                'operators': [],
                'affiliates': []
            }

            for offer in category.offer.values():
                kpi_plan = offer.kpi_current_plan
                category_data['offers'].append({
                    'key': offer.key,
                    'description': offer.description,
                    'kpi_stat': {
                        'calls_group_effective_count': offer.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': offer.kpi_stat.leads_effective_count,
                        'effective_percent': offer.kpi_stat.effective_percent,
                        'effective_rate': offer.kpi_stat.effective_rate,
                    },
                    'lead_container': {
                        'leads_non_trash_count': offer.lead_container.leads_non_trash_count,
                        'leads_approved_count': offer.lead_container.leads_approved_count,
                    },
                    'kpi_current_plan': {
                        'operator_efficiency': kpi_plan.operator_efficiency if kpi_plan else None,
                        'planned_approve': kpi_plan.planned_approve if kpi_plan else None,
                        'planned_buyout': kpi_plan.planned_buyout if kpi_plan else None,
                        'confirmation_price': kpi_plan.confirmation_price if kpi_plan else None,
                        'operator_effeciency_update_date': kpi_plan.operator_effeciency_update_date if kpi_plan else None,
                        'planned_approve_update_date': kpi_plan.planned_approve_update_date if kpi_plan else None,
                        'planned_buyout_update_date': kpi_plan.planned_buyout_update_date if kpi_plan else None,
                    },
                    'recommended_effeciency': {
                        'value': offer.recommended_effeciency.value if offer.recommended_effeciency else None},
                    'recommended_approve': {
                        'value': offer.recommended_approve.value if offer.recommended_approve else None},
                    'recommended_buyout': {
                        'value': offer.recommended_buyout.value if offer.recommended_buyout else None},
                    'recommended_confirmation_price': {
                        'value': offer.recommended_confirmation_price.value if offer.recommended_confirmation_price else None},
                    'corrections': {
                        'efficiency': offer.kpi_eff_need_correction_str,
                        'approve': offer.kpi_app_need_correction_str,
                        'buyout': offer.kpi_buyout_need_correction_str,
                        'confirmation_price': offer.kpi_confirmation_price_need_correction_str
                    }
                })

            for operator in category.operator_sorted:
                category_data['operators'].append({
                    'key': operator.key,
                    'kpi_stat': {
                        'calls_group_effective_count': operator.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': operator.kpi_stat.leads_effective_count,
                        'effective_percent': operator.kpi_stat.effective_percent,
                        'effective_rate': operator.kpi_stat.effective_rate,
                    }
                })

            for aff in category.aff.values():
                category_data['affiliates'].append({
                    'key': aff.key,
                    'kpi_stat': {
                        'calls_group_effective_count': aff.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': aff.kpi_stat.leads_effective_count,
                        'effective_percent': aff.kpi_stat.effective_percent,
                        'effective_rate': aff.kpi_stat.effective_rate,
                    }
                })

            result.append(category_data)
        logger.debug(f"Форматирование завершено, категорий: {len(result)}")
        return result

    def calculate_advanced_summary(self, stat):
        total_calls = total_leads = total_categories = total_offers = total_operators = 0
        for category in stat.category.values():
            total_calls += category.kpi_stat.calls_group_effective_count
            total_leads += category.kpi_stat.leads_effective_count
            total_categories += 1
            total_offers += len(category.offer)
            total_operators += len(category.operator)
        summary = {
            'total_categories': total_categories,
            'total_offers': total_offers,
            'total_operators': total_operators,
            'total_effective_calls': total_calls,
            'total_effective_leads': total_leads,
            'overall_efficiency': round(safe_div(total_leads, total_calls) * 100, 2) if total_calls > 0 else 0,
            'overall_conversion_rate': round(safe_div(total_leads, total_calls) * 100, 2) if total_calls > 0 else 0
        }
        logger.debug(f"Расширенная сводка: {summary}")
        return summary

    def extract_recommendations(self, stat):
        recommendations = []
        for category_name, category in stat.category.items():
            if category.recommended_effeciency and category.recommended_effeciency.value:
                recommendations.append({
                    'type': 'efficiency',
                    'category': category_name,
                    'current_value': round(category.kpi_stat.effective_rate, 2),
                    'recommended_value': round(category.recommended_effeciency.value, 2),
                    'comment': category.recommended_effeciency.comment
                })
            if category.recommended_approve and category.recommended_approve.value:
                recommendations.append({
                    'type': 'approve_rate',
                    'category': category_name,
                    'current_value': round(category.approve_percent_fact, 2) if category.approve_percent_fact else 0,
                    'recommended_value': round(category.recommended_approve.value, 2),
                    'comment': category.recommended_approve.comment
                })
        logger.debug(f"Извлечено {len(recommendations)} рекомендаций")
        return recommendations

    @action(detail=False, methods=['get'])
    def comparison(self, request):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if not date_from or not date_to:
            logger.warning("Отсутствуют date_from и date_to для сравнения")
            return Response({'error': 'date_from и date_to обязательны'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Сравнение аналитик за период {date_from} - {date_to}")
        try:
            analytics_viewset = KPIAnalyticsViewSet()
            simple_data = analytics_viewset.execute_kpi_queries_with_filters(
                {'date_from': date_from, 'date_to': date_to})
            simple_summary = analytics_viewset.calculate_summary(simple_data)

            advanced_stat = self.create_advanced_kpi_statistics({'date_from': date_from, 'date_to': date_to})
            advanced_summary = self.calculate_advanced_summary(advanced_stat)

            comparison_result = {
                'simple_analysis': simple_summary,
                'advanced_analysis': advanced_summary,
                'comparison': {
                    'records_count_diff': advanced_summary.get('total_categories', 0) - simple_summary.get('records_count', 0),
                    'efficiency_diff': advanced_summary.get('overall_efficiency', 0) - simple_summary.get('conversion_rate', 0)
                }
            }
            logger.info("Сравнение завершено")
            return Response(comparison_result)
        except Exception as e:
            logger.error(f"Ошибка при сравнении аналитик: {str(e)}")
            return Response({'error': f'Ошибка сравнения: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def columns_info(self, request):
        logger.info("Запрос информации о колонках")
        formatter = KPIOutputFormatter()
        headers = formatter._create_headers()
        columns_info = []
        for i, header in enumerate(headers):
            columns_info.append({
                'index': i,
                'header': header,
                'width': self._get_column_width(i),
                'type': self._get_column_type(i)
            })
        return Response({'columns': columns_info})

    def _get_column_width(self, index):
        widths = {
            0: 120, 1: 150, 2: 80, 3: 200, 4: 80, 5: 120, 6: 100, 7: 100, 8: 100, 10: 80,
            11: 80, 14: 80, 18: 100, 19: 100, 20: 100, 21: 100, 22: 100, 27: 80, 28: 100,
            29: 100, 30: 100, 34: 80, 36: 80, 38: 80, 40: 80
        }
        return widths.get(index, 100)

    def _get_column_type(self, index):
        if index in [6, 7, 18, 19, 27]:
            return 'number'
        elif index in [8, 10, 11, 14, 20, 21, 22, 28, 29, 30, 34, 36, 38, 40]:
            return 'float'
        else:
            return 'string'


class KpiDataViewSet(viewsets.ModelViewSet):
    queryset = KpiData.objects.all()
    serializer_class = KpiDataSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'offer_name', 'operator_name', 'date_from']

    @action(detail=False, methods=['post'])
    def refresh_data(self, request):
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        logger.info(f"Обновление данных KPI с {date_from} по {date_to}")
        try:
            KpiData.objects.filter(date_from=date_from, date_to=date_to).delete()
            analytics_viewset = KPIAnalyticsViewSet()
            raw_data = analytics_viewset.execute_kpi_queries_with_filters({'date_from': date_from, 'date_to': date_to})

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
                    effective_calls=item.get('calls_count', 0),
                    effective_leads=item.get('leads_count', 0),
                    effective_rate=item.get('conversion_rate', 0),
                    effective_percent=item.get('conversion_rate', 0),
                )
                records_created += 1

            logger.info(f"Обновление данных завершено, создано записей: {records_created}")
            return Response({'status': 'success', 'records_created': records_created})
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных KPI: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LegacyKPIAnalysisView(APIView):
    def post(self, request):
        logger.info("Legacy KPI анализ")
        try:
            params = {
                'date_from': request.data.get('B3', ''),
                'date_to': request.data.get('B4', ''),
                'group_rows': request.data.get('B6', 'Нет'),
                'advertiser': request.data.get('B7', '').lower(),
                'output': request.data.get('B8', 'Все'),
                'aff_id': request.data.get('B9', ''),
                'category': request.data.get('B10', '').lower(),
                'offer_id': request.data.get('B11', ''),
                'lv_op': request.data.get('B12', '').lower(),
            }

            analysis_viewset = KPIAdvancedAnalysisViewSet()
            result = analysis_viewset.advanced_analysis(request._request)

            logger.info("Legacy KPI анализ завершен")
            return Response(result.data)

        except Exception as e:
            logger.error(f"Ошибка в Legacy KPI анализе: {str(e)}")
            return Response({'error': str(e)}, status=400)


class LegacyFilterParamsView(APIView):
    def get(self, request):
        logger.info("Запрос доступных фильтров")
        return Response({
            'available_filters': {
                'output': ['Все', 'Есть активность', '--'],
                'group_rows': ['Да', 'Нет'],
                'advertisers': self.get_advertisers_list(),
                'categories': self.get_categories_list(),
            }
        })

    def get_advertisers_list(self):
        logger.debug("Получение списка рекламодателей")
        try:
            connection = connections['itrade']
            with connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT name FROM partners_subsystem WHERE name IS NOT NULL")
                results = [row[0] for row in cursor.fetchall()]
                logger.debug(f"Получено {len(results)} рекламодателей")
                return results
        except Exception as e:
            logger.error(f"Ошибка при получении списка рекламодателей: {str(e)}")
            return []

    def get_categories_list(self):
        logger.debug("Получение списка категорий")
        try:
            connection = connections['itrade']
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT name FROM partners_groupoffer 
                    WHERE name NOT IN ('Архив', 'Входящая линия') AND name IS NOT NULL
                """)
                results = [row[0] for row in cursor.fetchall()]
                logger.debug(f"Получено {len(results)} категорий")
                return results
        except Exception as e:
            logger.error(f"Ошибка при получении списка категорий: {str(e)}")
            return []