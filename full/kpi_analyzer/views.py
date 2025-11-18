import time
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .services.output_formatter import KPIOutputFormatter
from .services.db_service import DBService
from .services.kpi_analyzer import OpAnalyzeKPI
from .models import Spreadsheet, Sheet, Cell, Formula, PivotTable, Category, Offer, Operator, Affiliate, KpiData
from .serializers import (
    SpreadsheetSerializer, SheetSerializer, CellSerializer, FormulaSerializer, PivotTableSerializer,
    CategorySerializer, OfferSerializer, OperatorSerializer, AffiliateSerializer, KpiDataSerializer
)
from .services.formula_engine import FormulaEngine
from .pivot_engine import PivotEngine

logger = logging.getLogger(__name__)


class SpreadsheetViewSet(viewsets.ModelViewSet):
    queryset = Spreadsheet.objects.all().order_by('-id')
    serializer_class = SpreadsheetSerializer
    permission_classes = [AllowAny]
    pagination_class = None


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
        try:
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
            return Response({'status': 'success'})
        except Exception as e:
            logger.error(f"Ошибка массового обновления ячеек: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FormulaViewSet(viewsets.ModelViewSet):
    queryset = Formula.objects.all()
    serializer_class = FormulaSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def evaluate(self, request):
        formula = request.data.get('formula')
        sheet_data = request.data.get('sheet_data', {})
        try:
            engine = FormulaEngine()
            result = engine.evaluate_formula(formula, sheet_data)
            dependencies = engine.extract_dependencies(formula)
            return Response({'result': result, 'dependencies': dependencies})
        except Exception as e:
            logger.error(f"Ошибка вычисления формулы: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PivotTableViewSet(viewsets.ModelViewSet):
    queryset = PivotTable.objects.all()
    serializer_class = PivotTableSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        pivot_table = self.get_object()
        try:
            pivot_engine = PivotEngine()
            result = pivot_engine.generate_pivot(pivot_table)
            return Response({'data': result})
        except Exception as e:
            logger.error(f"Ошибка генерации сводной таблицы: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def available_fields(self, request):
        pivot_engine = PivotEngine()
        fields = pivot_engine.get_available_fields()
        return Response({'fields': fields})


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


class KPIAdvancedAnalysisViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def advanced_analysis(self, request):
        start_time = time.time()
        filter_params = request.data or {}
        response = {'success': False, 'data': []}

        logger.info(f"Запуск KPI анализа: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:
            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis(filter_params)

            # ОТЛАДОЧНАЯ ИНФОРМАЦИЯ
            logger.info(f"=== ОТЛАДОЧНАЯ ИНФОРМАЦИЯ ===")
            logger.info(f"Тип stat объекта: {type(stat)}")
            logger.info(f"Атрибуты stat: {dir(stat)}")
            logger.info(f"Количество категорий: {len(stat.category)}")

            if hasattr(stat, 'category'):
                logger.info(f"stat.category существует, количество: {len(stat.category)}")
            else:
                logger.info("stat.kpi_stat не существует")
                return Response({'success': False, 'error': 'Invalid stat structure'}, status=400)

            total_leads = 0
            total_calls = 0
            category_count = 0

            for cat_name, category in stat.category.items():
                category_count += 1
                logger.info(f"--- Категория #{category_count}: '{cat_name}' ---")
                logger.info(f"Тип категории: {type(category)}")
                logger.info(f"Атрибуты категории: {dir(category)}")

                if hasattr(category, 'kpi_stat'):
                    logger.info(f"category.kpi_stat существует")
                    if hasattr(category.kpi_stat, 'leads_effective_count'):
                        cat_leads = category.kpi_stat.leads_effective_count
                        total_leads += cat_leads
                        logger.info(f"  leads_effective_count: {cat_leads}")
                    else:
                        logger.info("  leads_effective_count отсутствует")

                    if hasattr(category.kpi_stat, 'calls_group_effective_count'):
                        cat_calls = category.kpi_stat.calls_group_effective_count
                        total_calls += cat_calls
                        logger.info(f"  calls_group_effective_count: {cat_calls}")
                    else:
                        logger.info("  calls_group_effective_count отсутствует")
                else:
                    logger.info("  category.kpi_stat отсутствует")

                # Проверяем наличие других возможных источников данных
                if hasattr(category, 'lead_container'):
                    logger.info(f"  lead_container: {category.lead_container}")

            logger.info(f"=== ИТОГО ===")
            logger.info(f"Всего категорий обработано: {category_count}")
            logger.info(f"Общее количество leads: {total_leads}")
            logger.info(f"Общее количество calls: {total_calls}")
            logger.info(f"=== КОНЕЦ ОТЛАДОЧНОЙ ИНФОРМАЦИИ ===")

            formatter = KPIOutputFormatter()
            result_data = formatter.format_for_frontend(
                stat,
                group_rows=filter_params.get('group_rows', 'Нет')
            )

            execution_time = round(time.time() - start_time, 2)

            response = {
                'success': True,
                'data': result_data['data'],
                'groups': result_data['groups'],
                'recommendations': result_data['recommendations'],
                'performance': {
                    'total_seconds': execution_time,
                    'leads_count': total_leads,
                    'calls_count': total_calls,
                }
            }

        except Exception as e:
            logger.error(f"Ошибка анализа KPI: {e}", exc_info=True)
            response = {'success': False, 'error': str(e), 'data': []}

        finally:
            execution_time = round(time.time() - start_time, 2)
            logger.info(f"KPI анализ завершён за {execution_time}s")

        return Response(response)

    @action(detail=False, methods=['post'])
    def full_structured_data(self, request):
        """
        Получение полных структурированных данных для FullDataPage
        Возвращает все данные в структурированном формате с полной информацией
        """
        start_time = time.time()
        filter_params = request.data or {}
        response = {'success': False, 'data': []}

        logger.info(
            f"Запуск полного KPI анализа для FullDataPage: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:
            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis(filter_params)

            # Отладочная информация
            if hasattr(stat, 'category'):
                logger.info(f"Обработано категорий: {len(stat.category)}")
            else:
                logger.error("Invalid stat structure - no category attribute")
                return Response({'success': False, 'error': 'Invalid stat structure'}, status=400)

            total_leads = 0
            total_calls = 0

            # Собираем статистику
            for cat_name, category in stat.category.items():
                if hasattr(category, 'kpi_stat'):
                    if hasattr(category.kpi_stat, 'leads_effective_count'):
                        total_leads += category.kpi_stat.leads_effective_count
                    if hasattr(category.kpi_stat, 'calls_group_effective_count'):
                        total_calls += category.kpi_stat.calls_group_effective_count

            formatter = KPIOutputFormatter()

            # Получаем структурированные данные
            result_data = formatter.format_for_frontend(
                stat,
                group_rows=filter_params.get('group_rows', 'Нет')
            )

            execution_time = round(time.time() - start_time, 2)

            response = {
                'success': True,
                'data': result_data['data'],
                'recommendations': result_data.get('recommendations', []),
                'performance': {
                    'total_seconds': execution_time,
                    'leads_count': total_leads,
                    'calls_count': total_calls,
                }
            }

        except Exception as e:
            logger.error(f"Ошибка полного анализа KPI: {e}", exc_info=True)
            response = {'success': False, 'error': str(e), 'data': []}

        finally:
            execution_time = round(time.time() - start_time, 2)
            logger.info(f"Полный KPI анализ завершён за {execution_time}s")

        return Response(response)

    @action(detail=False, methods=['post'])
    def full_data_table(self, request):
        """
        Получение данных в виде плоской таблицы для AG-Grid
        Возвращает все строки с полным набором колонок
        """
        start_time = time.time()
        filter_params = request.data or {}
        response = {'success': False, 'rows': []}

        logger.info(
            f"Запуск генерации полной таблицы KPI: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:
            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis(filter_params)

            formatter = KPIOutputFormatter()

            # Используем метод create_output_structure для получения всех данных в табличном формате
            table_data = formatter.create_output_structure(stat)

            if not table_data or len(table_data) < 2:
                response = {
                    'success': True,
                    'headers': [],
                    'rows': [],
                    'performance': {
                        'total_seconds': round(time.time() - start_time, 2),
                    }
                }
                return Response(response)

            # Первая строка - заголовки
            headers = table_data[0]
            # Остальные строки - данные
            rows_data = table_data[1:]

            # Преобразуем в формат для фронтенда
            formatted_rows = []
            for row_index, row in enumerate(rows_data):
                row_dict = {
                    'id': row_index,
                    'type': row[0] if len(row) > 0 else '',  # Тип данных из первой колонки
                }

                # Добавляем все колонки
                for col_index, value in enumerate(row):
                    if col_index < len(headers):
                        header = headers[col_index]
                        # Создаем понятные имена полей для AG-Grid
                        field_name = self._get_field_name(header, col_index)
                        row_dict[field_name] = value

                formatted_rows.append(row_dict)

            execution_time = round(time.time() - start_time, 2)

            response = {
                'success': True,
                'headers': headers,
                'rows': formatted_rows,
                'performance': {
                    'total_seconds': execution_time,
                }
            }

        except Exception as e:
            logger.error(f"Ошибка генерации полной таблицы KPI: {e}", exc_info=True)
            response = {'success': False, 'error': str(e), 'rows': []}

        return Response(response)

    def _get_field_name(self, header, col_index):
        """
        Преобразует заголовок в имя поля для AG-Grid
        """
        # Базовое преобразование русских заголовков в английские имена полей
        field_mapping = {
            "Тип данных": "type",
            "ID Оффер": "offer_id",
            "Оффер": "offer_name",
            "ID Вебмастер": "aff_id",
            "Оператор": "operator_name",
            "Ко-во звонков (эфф)": "calls_effective",
            "Ко-во продаж (эфф)": "leads_effective",
            "% эффективности": "effective_percent",
            "Эфф. факт": "effective_rate_fact",
            "Эфф. план": "effective_rate_plan",
            "Дата обновления": "effective_update_date",
            "Тип Плана": "plan_type",
            "Эфф. рекоммендация": "effective_recommendation",
            "Требуется коррекция": "effective_correction_needed",
            "Ко-во лидов (без треша)": "leads_non_trash",
            "Ко-во аппрувов": "leads_approved",
            "% аппрува факт": "approve_percent_fact",
            "% аппрува план": "approve_percent_plan",
            "% аппрува рекоммендация": "approve_recommendation",
            "Дата обновления аппрув": "approve_update_date",
            "Требуется коррекция аппрув": "approve_correction_needed",
            "% выкупа": "buyout_percent",
            "Ко-во выкупов": "leads_buyout",
            "% выкупа факт": "buyout_percent_fact",
            "% выкупа план": "buyout_percent_plan",
            "% выкупа рекоммендация": "buyout_recommendation",
            "Дата обновления выкупа": "buyout_update_date",
            "Требуется коррекция выкупа": "buyout_correction_needed",
            "[СВОД]": "summary",
            "Эфф. Рек.": "summary_effective_rec",
            "Коррекция?": "summary_effective_corr",
            "Апп. Рек.": "summary_approve_rec",
            "Коррекция?": "summary_approve_corr",
            "Чек Рек.": "summary_check_rec",
            "Коррекция?": "summary_check_corr",
            "Выкуп. Рек.": "summary_buyout_rec",
            "Коррекция?": "summary_buyout_corr",
            "Ссылка": "link"
        }

        if header in field_mapping:
            return field_mapping[header]
        else:
            # Генерируем имя на основе индекса, если заголовок не распознан
            return f"col_{col_index}"


class LegacyKPIAnalysisView(APIView):
    def post(self, request):
        viewset = KPIAdvancedAnalysisViewSet()
        result = viewset.advanced_analysis(request)
        return Response({
            'success': result.data.get('success', False),
            'data': result.data.get('data', []),
            'recommendations': result.data.get('recommendations', []),
        })


class LegacyFilterParamsView(APIView):
    def get(self, request):
        return Response({
            'available_filters': {
                'output': ['Все', 'Есть активность', '--'],
                'group_rows': ['Да', 'Нет'],
                'advertisers': self.get_advertisers_list(),
                'categories': self.get_categories_list(),
            }
        })

    def get_advertisers_list(self):
        query = "SELECT DISTINCT name FROM partners_subsystem WHERE name IS NOT NULL"
        return [row['name'] for row in DBService._execute_query(query, [])]

    def get_categories_list(self):
        query = """SELECT DISTINCT name FROM partners_groupoffer 
                   WHERE name NOT IN ('Архив', 'Входящая линия') AND name IS NOT NULL"""
        return [row['name'] for row in DBService._execute_query(query, [])]


class KpiDataViewSet(viewsets.ModelViewSet):
    queryset = KpiData.objects.all()
    serializer_class = KpiDataSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'offer_name', 'operator_name', 'date_from']

    @action(detail=False, methods=['post'])
    def test_compatibility(self, request):
        try:
            kpi_data = DBService.get_kpi_plans_data()
            leads_data = DBService.get_leads({})
            calls_data = DBService.get_calls({})
            containers_data = DBService.get_leads_container({})
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