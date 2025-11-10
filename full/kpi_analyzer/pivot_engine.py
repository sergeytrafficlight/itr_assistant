import pandas as pd
import numpy as np
from typing import Dict, List, Any
from django.db.models import Sum, Count, Avg, Max, Min


class PivotEngine:
    def __init__(self):
        self.aggregations = {
            'SUM': 'sum',
            'COUNT': 'count',
            'AVG': 'mean',
            'MIN': 'min',
            'MAX': 'max'
        }

    def generate_pivot(self, pivot_config: Dict) -> Dict[str, Any]:
        """Генерация сводной таблицы на основе конфигурации"""

        try:
            # ИСПРАВЛЕНИЕ: используем прямые SQL запросы для KPI данных
            from django.db import connections

            # Получаем данные напрямую из БД через существующие методы
            date_from = pivot_config.get('filters', {}).get('date_from')
            date_to = pivot_config.get('filters', {}).get('date_to')

            if date_from and date_to:
                # Используем существующие методы из views
                from .views import KPIAnalyticsViewSet
                analytics_viewset = KPIAnalyticsViewSet()
                raw_data = analytics_viewset.execute_kpi_queries(
                    date_from, date_to, None, None, None, None
                )

                if not raw_data:
                    return {'rows': [], 'columns': [], 'data': [], 'summary': {}}

                df = pd.DataFrame(raw_data)
            else:
                # Если нет фильтров по дате, используем тестовые данные или возвращаем пустые
                df = self._get_sample_data()
                if df.empty:
                    return {'rows': [], 'columns': [], 'data': [], 'summary': {}}

            # Применение фильтров
            filters = pivot_config.get('filters', {})
            for field, value in filters.items():
                if value and field in df.columns:
                    if field in ['date_from', 'date_to']:
                        if 'operator' in value and 'value' in value:
                            operator = value['operator']
                            filter_value = value['value']
                            if operator == 'gte':
                                df = df[df[field] >= filter_value]
                            elif operator == 'lte':
                                df = df[df[field] <= filter_value]
                    else:
                        df = df[df[field].astype(str).str.contains(str(value), case=False, na=False)]

            # Настройки группировки из конфигурации
            rows = pivot_config.get('rows', [])
            columns = pivot_config.get('columns', [])
            values = pivot_config.get('values', [])
            aggregation = pivot_config.get('aggregation', 'SUM')

            # Создание сводной таблицы
            if rows and values:
                # Проверяем что указанные поля существуют в DataFrame
                valid_rows = [r for r in rows if r in df.columns]
                valid_columns = [c for c in columns if c in df.columns] if columns else []
                valid_values = [v for v in values if v in df.columns]

                if valid_rows and valid_values:
                    pivot_df = df.pivot_table(
                        index=valid_rows,
                        columns=valid_columns if valid_columns else None,
                        values=valid_values,
                        aggfunc=self.aggregations.get(aggregation, 'sum'),
                        fill_value=0,
                        margins=True,
                        margins_name='Итого'
                    )
                else:
                    # Если нет валидных полей, возвращаем исходные данные
                    pivot_df = df
            else:
                # Если нет строк для группировки, возвращаем исходные данные
                pivot_df = df

            # Конвертация в формат для фронтенда
            result = self._dataframe_to_dict(pivot_df, pivot_config)

            # Добавляем сводную статистику
            result['summary'] = self._calculate_summary(df, values, aggregation)

            return result

        except Exception as e:
            print(f"❌ Ошибка генерации pivot: {str(e)}")
            return {'rows': [], 'columns': [], 'data': [], 'summary': {}, 'error': str(e)}

    def _get_sample_data(self):
        """Генерация тестовых данных для демонстрации"""
        try:
            # Создаем тестовые данные на основе available_fields
            data = {
                'category': ['Электроника', 'Электроника', 'Одежда', 'Одежда', 'Электроника'],
                'offer_name': ['Телефон', 'Ноутбук', 'Футболка', 'Джинсы', 'Планшет'],
                'operator_name': ['Оператор А', 'Оператор Б', 'Оператор А', 'Оператор Б', 'Оператор А'],
                'calls_count': [100, 150, 80, 120, 90],
                'leads_count': [20, 30, 15, 25, 18],
                'effective_calls': [80, 120, 60, 100, 70],
                'effective_leads': [15, 25, 12, 20, 14],
                'effective_rate': [5.33, 4.80, 5.00, 5.00, 5.00],
                'effective_percent': [18.75, 20.83, 20.00, 20.00, 20.00],
                'date_from': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'],
                'date_to': ['2024-01-31', '2024-01-31', '2024-01-31', '2024-01-31', '2024-01-31']
            }
            return pd.DataFrame(data)
        except Exception as e:
            print(f"❌ Ошибка создания тестовых данных: {e}")
            return pd.DataFrame()

    def _dataframe_to_dict(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """Конвертация DataFrame в словарь для фронтенда"""
        result = {
            'rows': [],
            'columns': [],
            'data': []
        }

        if df.empty:
            return result

        # Обработка MultiIndex для строк
        if isinstance(df.index, pd.MultiIndex):
            result['rows'] = [
                {f'level_{i}': val for i, val in enumerate(idx)}
                for idx in df.index
            ]
        else:
            result['rows'] = [{'level_0': idx} for idx in df.index]

        # Обработка MultiIndex для колонок
        if isinstance(df.columns, pd.MultiIndex):
            result['columns'] = [
                {f'level_{i}': val for i, val in enumerate(col)}
                for col in df.columns
            ]
        else:
            result['columns'] = [{'level_0': col} for col in df.columns]

        # Данные
        if hasattr(df, 'values'):
            # Для pivot таблиц
            result['data'] = df.values.tolist()
        else:
            # Для обычных DataFrame
            result['data'] = df.tolist() if hasattr(df, 'tolist') else []

        return result

    def _calculate_summary(self, df: pd.DataFrame, values: List[str], aggregation: str) -> Dict:
        """Расчет сводной статистики"""
        summary = {}

        for value_field in values:
            if value_field in df.columns:
                if aggregation == 'SUM':
                    summary[value_field] = df[value_field].sum()
                elif aggregation == 'AVG':
                    summary[value_field] = df[value_field].mean()
                elif aggregation == 'MAX':
                    summary[value_field] = df[value_field].max()
                elif aggregation == 'MIN':
                    summary[value_field] = df[value_field].min()
                elif aggregation == 'COUNT':
                    summary[value_field] = df[value_field].count()

        return summary

    def get_available_fields(self) -> List[Dict[str, str]]:
        """Получение доступных полей для сводной таблицы на основе google_kpi.txt"""
        return [
            # Группировки
            {'field': 'category', 'name': 'Категория', 'type': 'string', 'grouping': True},
            {'field': 'offer_name', 'name': 'Оффер', 'type': 'string', 'grouping': True},
            {'field': 'operator_name', 'name': 'Оператор', 'type': 'string', 'grouping': True},
            {'field': 'date_from', 'name': 'Дата начала', 'type': 'date', 'grouping': True},
            {'field': 'date_to', 'name': 'Дата окончания', 'type': 'date', 'grouping': True},

            # Значения для агрегации
            {'field': 'calls_count', 'name': 'Звонки', 'type': 'number', 'aggregation': True},
            {'field': 'leads_count', 'name': 'Лиды', 'type': 'number', 'aggregation': True},
            {'field': 'effective_rate', 'name': 'Эффективность', 'type': 'number', 'aggregation': True},
            {'field': 'effective_percent', 'name': 'Процент эффективности', 'type': 'percentage', 'aggregation': True},
            {'field': 'avg_duration', 'name': 'Средняя длительность', 'type': 'number', 'aggregation': True},

            # KPI метрики из google_kpi.txt
            {'field': 'effective_calls', 'name': 'Эффективные звонки', 'type': 'number', 'aggregation': True},
            {'field': 'effective_leads', 'name': 'Эффективные лиды', 'type': 'number', 'aggregation': True},
            {'field': 'non_trash_leads', 'name': 'Лиды без треша', 'type': 'number', 'aggregation': True},
            {'field': 'approved_leads', 'name': 'Аппрувленные лиды', 'type': 'number', 'aggregation': True},
            {'field': 'buyout_count', 'name': 'Выкупленные лиды', 'type': 'number', 'aggregation': True},
        ]

    def create_pivot_config(self, name: str, rows: List[str], columns: List[str],
                            values: List[str], aggregation: str = 'SUM') -> Dict:
        """Создание конфигурации сводной таблиции"""
        return {
            'name': name,
            'rows': rows,
            'columns': columns,
            'values': values,
            'aggregation': aggregation,
            'filters': {}
        }