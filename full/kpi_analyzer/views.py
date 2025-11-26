import time
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import permission_classes
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from datetime import datetime
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .services.output_formatter import KPIOutputFormatter
from .services.db_service import DBService
from .services.kpi_analyzer import OpAnalyzeKPI
from .models import Spreadsheet, Sheet, Cell, Formula, PivotTable, KpiData
from .serializers import (
    SpreadsheetSerializer, SheetSerializer, CellSerializer, FormulaSerializer,
    PivotTableSerializer, KpiDataSerializer
)
from .services.formula_engine import FormulaEngine
from .pivot_engine import PivotEngine

logger = logging.getLogger(__name__)


class PublicTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            pass
        return response


class UserRegistrationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')

        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Пользователь с таким логином уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_active=True
        )

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'message': 'Пользователь успешно создан'
        }, status=status.HTTP_201_CREATED)


class SpreadsheetViewSet(viewsets.ModelViewSet):
    queryset = Spreadsheet.objects.all().order_by('-id')
    serializer_class = SpreadsheetSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    pagination_class = None


class SheetViewSet(viewsets.ModelViewSet):
    queryset = Sheet.objects.all()
    serializer_class = SheetSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]


@permission_classes([IsAuthenticated, IsAdminUser])
class AdminStatsView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        today = datetime.now().date()

        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'inactive_users': User.objects.filter(is_active=False).count(),
            'new_users_today': User.objects.filter(date_joined__date=today).count(),
        }

        return Response(stats)


@permission_classes([IsAuthenticated, IsAdminUser])
class UserListView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        users = User.objects.all().order_by('-date_joined')
        user_data = []

        for user in users:
            user_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
            })

        return Response(user_data)

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        is_active = request.data.get('is_active', True)

        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Пользователь с таким логином уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Пользователь с таким email уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            is_active=is_active
        )

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'date_joined': user.date_joined
        }, status=status.HTTP_201_CREATED)


@permission_classes([IsAuthenticated, IsAdminUser])
class UserDetailView(APIView):
    authentication_classes = [JWTAuthentication]

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {'error': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        if 'is_active' in request.data:
            user.is_active = request.data['is_active']

        if 'password' in request.data:
            user.password = make_password(request.data['password'])

        user.save()

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active
        })

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)

            if user == request.user:
                return Response(
                    {'error': 'Нельзя удалить собственный аккаунт'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        except User.DoesNotExist:
            return Response(
                {'error': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )


@permission_classes([IsAuthenticated, IsAdminUser])
class AdminAuthView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser
        })


class CellViewSet(viewsets.ModelViewSet):
    queryset = Cell.objects.all()
    serializer_class = CellSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

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
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

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
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

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


# Эндпоинты для справочников (используют itrade)
@permission_classes([IsAuthenticated])
class CategoryListView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            query = """
            SELECT DISTINCT name 
            FROM partners_groupoffer 
            WHERE name NOT IN ('Архив', 'Входящая линия') 
            AND name IS NOT NULL 
            AND name != ''
            ORDER BY name
            """
            results = DBService._execute_query(query, [])
            categories = [row['name'] for row in results if row['name']]
            return Response(categories)
        except Exception as e:
            logger.error(f"Ошибка получения категорий: {e}")
            return Response([], status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@permission_classes([IsAuthenticated])
class AdvertiserListView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            query = """
            SELECT DISTINCT name 
            FROM partners_subsystem 
            WHERE 1=1
            AND system = 'traffic_light' 
            AND name IS NOT NULL 
            AND name != ''
            ORDER BY name
            """
            results = DBService._execute_query(query, [])
            advertisers = [row['name'] for row in results if row['name']]
            return Response(advertisers)
        except Exception as e:
            logger.error(f"Ошибка получения advertisers: {e}")
            return Response([], status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class KPIAdvancedAnalysisViewSet(viewsets.ViewSet):
    permission_classes = []
    authentication_classes = []

    @action(detail=False, methods=['post'])
    def advanced_analysis(self, request):
        start_time = time.time()
        filter_params = request.data or {}
        response = {'success': False, 'data': []}

        logger.info(f"Запуск KPI анализа: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:

            kpi_plans = DBService.get_kpi_plans_data()
            offers = DBService.get_offers(filter_params)
            leads = DBService.get_leads(filter_params)
            calls = DBService.get_calls(filter_params)
            leads_container = DBService.get_leads_container(filter_params)

            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis_with_data(
                kpi_plans_data=kpi_plans,
                offers_data=offers,
                leads_data=leads,
                calls_data=calls,
                leads_container_data=leads_container,
                filters=filter_params
            )

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
                    'leads_count': len(leads),
                    'calls_count': len(calls),
                }
            }

        except Exception as e:
            logger.error(f"Ошибка анализа KPI: {e}", exc_info=True)
            response = {'success': False, 'error': str(e), 'data': []}

        return Response(response)

    @action(detail=False, methods=['post'])
    def full_structured_data(self, request):
        start_time = time.time()
        filter_params = request.data or {}
        response = {'success': False, 'data': []}

        logger.info(
            f"Запуск полного KPI анализа для FullDataPage: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:
            kpi_plans = DBService.get_kpi_plans_data()
            offers = DBService.get_offers(filter_params)
            leads = DBService.get_leads(filter_params)
            calls = DBService.get_calls(filter_params)
            leads_container = DBService.get_leads_container(filter_params)

            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis_with_data(
                kpi_plans, offers, leads, calls, leads_container, filter_params
            )

            if hasattr(stat, 'category'):
                logger.info(f"Обработано категорий: {len(stat.category)}")
            else:
                logger.error("Invalid stat structure - no category attribute")
                return Response({'success': False, 'error': 'Invalid stat structure'}, status=400)

            total_leads = 0
            total_calls = 0

            for cat_name, category in stat.category.items():
                if hasattr(category, 'kpi_stat'):
                    if hasattr(category.kpi_stat, 'leads_effective_count'):
                        total_leads += category.kpi_stat.leads_effective_count
                    if hasattr(category.kpi_stat, 'calls_group_effective_count'):
                        total_calls += category.kpi_stat.calls_group_effective_count

            formatter = KPIOutputFormatter()
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
        start_time = time.time()
        filter_params = request.data or {}
        response = {'success': False, 'rows': []}

        logger.info(
            f"Запуск генерации полной таблицы KPI: {filter_params.get('date_from')} - {filter_params.get('date_to')}")

        try:
            kpi_plans = DBService.get_kpi_plans_data()
            offers = DBService.get_offers(filter_params)
            leads = DBService.get_leads(filter_params)
            calls = DBService.get_calls(filter_params)
            leads_container = DBService.get_leads_container(filter_params)

            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis_with_data(
                kpi_plans, offers, leads, calls, leads_container, filter_params
            )

            formatter = KPIOutputFormatter()
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

            headers = table_data[0]
            rows_data = table_data[1:]

            formatted_rows = []
            for row_index, row in enumerate(rows_data):
                row_dict = {
                    'id': row_index,
                    'type': row[0] if len(row) > 0 else '',
                }

                for col_index, value in enumerate(row):
                    if col_index < len(headers):
                        header = headers[col_index]
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
            return f"col_{col_index}"


class LegacyKPIAnalysisView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        viewset = KPIAdvancedAnalysisViewSet()
        result = viewset.advanced_analysis(request)
        return Response({
            'success': result.data.get('success', False),
            'data': result.data.get('data', []),
            'recommendations': result.data.get('recommendations', []),
        })


class LegacyFilterParamsView(APIView):
    permission_classes = []
    authentication_classes = []

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
        query = """
        SELECT DISTINCT name 
        FROM partners_subsystem 
        WHERE 1=1
        AND system = 'traffic_light' 
        AND name IS NOT NULL 
        AND name != ''
        ORDER BY name
        """
        try:
            results = DBService._execute_query(query, [])
            return [row['name'] for row in results if row['name']]
        except Exception as e:
            logger.error(f"Ошибка получения advertisers: {e}")
            return []

    def get_categories_list(self):
        query = """SELECT DISTINCT name FROM partners_groupoffer 
                   WHERE name NOT IN ('Архив', 'Входящая линия') AND name IS NOT NULL"""
        try:
            results = DBService._execute_query(query, [])
            return [row['name'] for row in results if row['name']]
        except Exception as e:
            logger.error(f"Ошибка получения категорий: {e}")
            return []


class KpiDataViewSet(viewsets.ModelViewSet):
    queryset = KpiData.objects.all()
    serializer_class = KpiDataSerializer
    permission_classes = []
    authentication_classes = []
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