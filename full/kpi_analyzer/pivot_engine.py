import pandas as pd
import numpy as np
from typing import Dict, List, Any
from django.db.models import Sum, Count, Avg, Max, Min
from .services.db_service import DBService
from .services.kpi_analyzer import OpAnalyzeKPI


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
            # Получаем фильтры
            filters = pivot_config.get('filters', {})

            # Используем существующую систему анализа KPI
            analyzer = OpAnalyzeKPI()
            stat = analyzer.run_analysis(filters)

            # Конвертируем данные в DataFrame
            df = self._convert_stat_to_dataframe(stat, filters)

            if df.empty:
                return {'rows': [], 'columns': [], 'data': [], 'summary': {}}

            # Настройки группировки из конфигурации
            rows = pivot_config.get('rows', [])
            columns = pivot_config.get('columns', [])
            values = pivot_config.get('values', [])
            aggregation = pivot_config.get('aggregation', 'SUM')

            # Создание сводной таблицы
            if rows and values:
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
                    pivot_df = df
            else:
                pivot_df = df

            # Конвертация в формат для фронтенда
            result = self._dataframe_to_dict(pivot_df, pivot_config)
            result['summary'] = self._calculate_summary(df, values, aggregation)

            return result

        except Exception as e:
            print(f"❌ Ошибка генерации pivot: {str(e)}")
            return {'rows': [], 'columns': [], 'data': [], 'summary': {}, 'error': str(e)}

    def _convert_stat_to_dataframe(self, stat, filters: Dict) -> pd.DataFrame:
        """Конвертация Stat объекта в DataFrame"""
        rows = []

        for cat_name, category in stat.category.items():
            # Данные категории
            cat_row = {
                'category': cat_name,
                'type': 'category',
                'calls_count': category.kpi_stat.calls_group_effective_count,
                'leads_count': category.kpi_stat.leads_effective_count,
                'effective_rate': category.kpi_stat.effective_rate,
                'effective_percent': category.kpi_stat.effective_percent,
                'non_trash_leads': category.lead_container.leads_non_trash_count,
                'approved_leads': category.lead_container.leads_approved_count,
                'buyout_count': category.lead_container.leads_buyout_count,
                'date_from': filters.get('date_from', ''),
                'date_to': filters.get('date_to', '')
            }
            rows.append(cat_row)

            # Данные офферов в категории
            for offer_id, offer in category.offer.items():
                offer_row = {
                    'category': cat_name,
                    'offer_name': offer.description,
                    'type': 'offer',
                    'calls_count': offer.kpi_stat.calls_group_effective_count,
                    'leads_count': offer.kpi_stat.leads_effective_count,
                    'effective_rate': offer.kpi_stat.effective_rate,
                    'effective_percent': offer.kpi_stat.effective_percent,
                    'non_trash_leads': offer.lead_container.leads_non_trash_count,
                    'approved_leads': offer.lead_container.leads_approved_count,
                    'buyout_count': offer.lead_container.leads_buyout_count,
                    'date_from': filters.get('date_from', ''),
                    'date_to': filters.get('date_to', '')
                }
                rows.append(offer_row)

            # Данные операторов в категории
            for op_name, operator in category.operator.items():
                op_row = {
                    'category': cat_name,
                    'operator_name': op_name,
                    'type': 'operator',
                    'calls_count': operator.kpi_stat.calls_group_effective_count,
                    'leads_count': operator.kpi_stat.leads_effective_count,
                    'effective_rate': operator.kpi_stat.effective_rate,
                    'effective_percent': operator.kpi_stat.effective_percent,
                    'date_from': filters.get('date_from', ''),
                    'date_to': filters.get('date_to', '')
                }
                rows.append(op_row)

        return pd.DataFrame(rows)

    def _dataframe_to_dict(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """Конвертация DataFrame в словарь для фронтенда"""
        # ... существующий код без изменений ...
        result = {
            'rows': [],
            'columns': [],
            'data': []
        }

        if df.empty:
            return result

        if isinstance(df.index, pd.MultiIndex):
            result['rows'] = [
                {f'level_{i}': val for i, val in enumerate(idx)}
                for idx in df.index
            ]
        else:
            result['rows'] = [{'level_0': idx} for idx in df.index]

        if isinstance(df.columns, pd.MultiIndex):
            result['columns'] = [
                {f'level_{i}': val for i, val in enumerate(col)}
                for col in df.columns
            ]
        else:
            result['columns'] = [{'level_0': col} for col in df.columns]

        if hasattr(df, 'values'):
            result['data'] = df.values.tolist()
        else:
            result['data'] = df.tolist() if hasattr(df, 'tolist') else []

        return result

    def _calculate_summary(self, df: pd.DataFrame, values: List[str], aggregation: str) -> Dict:
        """Расчет сводной статистики"""
        # ... существующий код без изменений ...
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
        """Получение доступных полей для сводной таблицы"""
        # ... существующий код без изменений ...
        return [
            {'field': 'category', 'name': 'Категория', 'type': 'string', 'grouping': True},
            {'field': 'offer_name', 'name': 'Оффер', 'type': 'string', 'grouping': True},
            {'field': 'operator_name', 'name': 'Оператор', 'type': 'string', 'grouping': True},
            {'field': 'date_from', 'name': 'Дата начала', 'type': 'date', 'grouping': True},
            {'field': 'date_to', 'name': 'Дата окончания', 'type': 'date', 'grouping': True},
            {'field': 'calls_count', 'name': 'Звонки', 'type': 'number', 'aggregation': True},
            {'field': 'leads_count', 'name': 'Лиды', 'type': 'number', 'aggregation': True},
            {'field': 'effective_rate', 'name': 'Эффективность', 'type': 'number', 'aggregation': True},
            {'field': 'effective_percent', 'name': 'Процент эффективности', 'type': 'percentage', 'aggregation': True},
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