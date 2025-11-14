from django.db import connections, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
import logging
import time
import gc
from datetime import datetime

from .services.output_formatter import KPIOutputFormatter
from .services.db_service import DBService
from .services.kpi_analyzer import Stat
from .services.engine_call_efficiency2 import EngineCallEfficiency2
from .services.statistics import safe_div
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
from .services.formula_engine import FormulaEngine
from .pivot_engine import PivotEngine

logger = logging.getLogger(__name__)


# === СПРАВОЧНЫЕ ViewSet'ы ===
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
            return Response({'result': result, 'dependencies': dependencies})
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


# === СПРАВОЧНИКИ ===
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
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


# === НОВЫЙ АНАЛИЗ KPI ===
class KPIAdvancedAnalysisViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def advanced_analysis(self, request):
        logger.info(">>> Анализ KPI данных")
        start_time = time.time()
        filter_params = request.data or {}
        logger.info(f"Период: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:
            # === 1. KPI планы ===
            kpi_plans_data = DBService.get_kpi_plans_data()
            logger.info(f"Загружено KPI планов: {len(kpi_plans_data)}")

            # === 2. Статистика ===
            stat = Stat()

            # === 3. ЛИДЫ — БАТЧ ПО id > last_id ===
            leads_count = 0
            last_lead_id = 0
            batch_size = 3000
            max_leads = 100000
            logger.info(">>> Загрузка лидов...")
            while leads_count < max_leads:
                batch = DBService.get_leads_batch_exact(filter_params, last_lead_id, batch_size)
                if not batch:
                    break
                for lead in batch:
                    stat.push_lead(lead)
                leads_count += len(batch)
                last_lead_id = batch[-1]['call_eff_crm_lead_id']
                logger.info(f"Лиды: {leads_count}")
                del batch
                gc.collect()
            logger.info(f">>> Лиды загружены: {leads_count}")

            # === 4. ЗВОНКИ — БАТЧ ПО id > last_id ===
            calls_count = 0
            last_call_id = 0
            batch_size = 500
            max_calls = 50000
            logger.info(">>> Загрузка звонков...")
            while calls_count < max_calls:
                batch = DBService.get_calls_batch_exact(filter_params, last_call_id, batch_size)
                if not batch:
                    break
                for call in batch:
                    stat.push_call(call)
                calls_count += len(batch)
                last_call_id = batch[-1]['call_eff_id']
                logger.info(f"Звонки: {calls_count}")
                del batch
                gc.collect()
            logger.info(f">>> Звонки загружены: {calls_count}")

            # === 5. КОНТЕЙНЕРЫ ЛИДОВ ===
            containers_count = 0
            last_container_id = 0
            batch_size = 10000
            max_containers = 200000
            logger.info(">>> Загрузка контейнеров...")
            while containers_count < max_containers:
                batch = DBService.get_leads_container_batch_exact(filter_params, last_container_id, batch_size)
                if not batch:
                    break
                for lc in batch:
                    stat.push_lead_container(lc)
                containers_count += len(batch)
                last_container_id = batch[-1]['lead_container_crm_lead_id']
                if containers_count % 20000 == 0:
                    logger.info(f"Контейнеры: {containers_count}")
                del batch
                gc.collect()
            logger.info(f">>> Контейнеры загружены: {containers_count}")

            # === 6. ФИНАЛИЗАЦИЯ ===
            logger.info(">>> Финализация (EngineCallEfficiency2)")
            stat.finalize(kpi_plans_data)

            # === 7. ОТЧЁТ ===
            formatter = KPIOutputFormatter()
            result_data = formatter.format_for_frontend(stat, group_rows=filter_params.get('group_rows', 'Нет'))
            execution_time = time.time() - start_time

            response = {
                'success': True,
                'data': result_data['data'],
                'groups': result_data['groups'],
                'recommendations': result_data['recommendations'],
                'global_stats': {
                    'actual_data_overview': {
                        'period_analyzed': f"{filter_params.get('date_from', 'не указан')} - {filter_params.get('date_to', 'сегодня')}",
                        'leads_analyzed': leads_count,
                        'calls_analyzed': calls_count,
                        'containers_analyzed': containers_count,
                        'kpi_plans_used': len(kpi_plans_data),
                        'categories_found': len(stat.category),
                        'kpi_logic': 'НОВАЯ ЛОГИКА (EngineCallEfficiency2)'
                    },
                    'efficiency_metrics': {
                        'effective_calls': sum(c.kpi_stat.calls_group_effective_count for c in stat.category.values()),
                        'effective_leads': sum(c.kpi_stat.leads_effective_count for c in stat.category.values()),
                        'conversion_rate': f"{safe_div(sum(c.kpi_stat.leads_effective_count for c in stat.category.values()), leads_count) * 100:.2f}%" if leads_count else "N/A",
                    },
                    'performance': {
                        'total_seconds': round(execution_time, 2),
                        'leads_per_second': round(leads_count / execution_time, 1) if execution_time > 0 else 0,
                        'calls_per_second': round(calls_count / execution_time, 1) if execution_time > 0 else 0,
                        'optimization': 'ЭТАЛОННЫЕ БАТЧИ + id > last_id'
                    }
                }
            }

        except Exception as e:
            logger.error(f"ОШИБКА анализа: {e}", exc_info=True)
            response = {'success': False, 'error': str(e), 'data': []}

        logger.info(f">>> Анализ завершён за {time.time() - start_time:.2f}с")
        return Response(response)


    @action(detail=False, methods=['post'])
    def parallel_analysis(self, request):
        logger.info(">>> Параллельный анализ KPI (новая логика)")
        start_time = time.time()
        filter_params = request.data or {}

        try:
            # === 1. KPI ===
            kpi_plans_data = DBService.get_kpi_plans_data()
            logger.info(f"KPI планов: {len(kpi_plans_data)}")

            # === 2. ПАРАЛЛЕЛЬНАЯ ЗАГРУЗКА ===
            # (предполагается, что DBService.execute_parallel_queries существует)
            offers_data, leads_data, leads_container_data, calls_data = DBService.execute_parallel_queries(filter_params)

            # === 3. ОБРАБОТКА ===
            stat = Stat()
            for lead in leads_data:
                stat.push_lead(lead)
            for call in calls_data:
                stat.push_call(call)
            for lc in leads_container_data:
                stat.push_lead_container(lc)

            # === 4. ФИНАЛИЗАЦИЯ ===
            stat.finalize(kpi_plans_data)

            # === 5. ОТЧЁТ ===
            formatter = KPIOutputFormatter()
            result_data = formatter.format_for_frontend(stat, group_rows=filter_params.get('group_rows', 'Нет'))
            execution_time = time.time() - start_time

            response = {
                'success': True,
                'data': result_data['data'],
                'groups': result_data['groups'],
                'recommendations': result_data['recommendations'],
                'global_stats': {
                    'actual_data_overview': {
                        'leads_analyzed': len(leads_data),
                        'calls_analyzed': len(calls_data),
                        'containers_analyzed': len(leads_container_data),
                        'kpi_plans_used': len(kpi_plans_data),
                        'categories_found': len(stat.category),
                        'kpi_logic': 'ПАРАЛЛЕЛЬНО + НОВАЯ ЛОГИКА'
                    },
                    'performance': {
                        'total_seconds': round(execution_time, 2),
                        'optimization': 'ПАРАЛЛЕЛЬНО + ЭТАЛОН'
                    }
                }
            }

        except Exception as e:
            logger.error(f"ОШИБКА параллельного анализа: {e}", exc_info=True)
            response = {'success': False, 'error': str(e)}

        logger.info(f">>> Параллельный анализ завершён за {time.time() - start_time:.2f}с")
        return Response(response)


# === Legacy API ===
class LegacyKPIAnalysisView(APIView):
    def post(self, request):
        logger.info("Legacy KPI анализ (перенаправление)")
        viewset = KPIAdvancedAnalysisViewSet()
        result = viewset.advanced_analysis(request)
        return Response({
            'success': result.data.get('success', False),
            'data': result.data.get('data', []),
            'recommendations': result.data.get('recommendations', []),
            'global_stats': result.data.get('global_stats', {}),
        })


class LegacyFilterParamsView(APIView):
    def get(self, request):
        logger.info("Запрос фильтров")
        return Response({
            'available_filters': {
                'output': ['Все', 'Есть активность', '--'],
                'group_rows': ['Да', 'Нет'],
                'advertisers': self.get_advertisers_list(),
                'categories': self.get_categories_list(),
            }
        })

    def get_advertisers_list(self):
        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute("SELECT DISTINCT name FROM partners_subsystem WHERE name IS NOT NULL")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка рекламодателей: {e}")
            return []

    def get_categories_list(self):
        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT name FROM partners_groupoffer
                    WHERE name NOT IN ('Архив', 'Входящая линия') AND name IS NOT NULL
                """)
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка категорий: {e}")
            return []


class KpiDataViewSet(viewsets.ModelViewSet):
    queryset = KpiData.objects.all()
    serializer_class = KpiDataSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'offer_name', 'operator_name', 'date_from']

    @action(detail=False, methods=['post'])
    def test_compatibility(self, request):
        try:
            kpi_list = EngineCallEfficiency2.KpiList()
            stat = Stat()
            test_params = {'date_from': '2024-01-01', 'date_to': '2024-01-02'}
            kpi_data = DBService.get_kpi_plans_data()
            leads_data = DBService.get_leads(test_params)
            calls_data = DBService.get_calls(test_params)
            containers_data = DBService.get_leads_container(test_params)
            return Response({
                'success': True,
                'kpi_count': len(kpi_data),
                'leads_count': len(leads_data),
                'calls_count': len(calls_data),
                'containers_count': len(containers_data),
                'compatibility': 'OK'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'compatibility': 'BROKEN'
            })