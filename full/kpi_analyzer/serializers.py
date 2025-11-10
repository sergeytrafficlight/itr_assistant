from rest_framework import serializers
from .models import (Spreadsheet, Sheet, Cell, Formula, PivotTable, KpiData,
                     Category, Offer, Operator, Affiliate)


class CellSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cell
        fields = ['id', 'sheet', 'row', 'col', 'value', 'formula', 'computed_value', 'style', 'dependency_list']


class SheetSerializer(serializers.ModelSerializer):
    cells = CellSerializer(many=True, read_only=True)

    class Meta:
        model = Sheet
        fields = ['id', 'spreadsheet', 'name', 'order', 'data', 'config', 'cells']


class SpreadsheetSerializer(serializers.ModelSerializer):
    sheets = SheetSerializer(many=True, read_only=True)

    class Meta:
        model = Spreadsheet
        fields = ['id', 'name', 'description', 'created_at', 'updated_at', 'sheets']


class FormulaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Formula
        fields = ['id', 'name', 'formula_text', 'formula_type', 'description', 'category']


class PivotTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = PivotTable
        fields = ['id', 'spreadsheet', 'name', 'config', 'data_range', 'created_at']


class KpiDataSerializer(serializers.ModelSerializer):
    """Сериализатор для KPI данных сводных таблиц"""

    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = KpiData
        fields = [
            'id', 'category', 'category_display', 'offer_name', 'operator_name', 'affiliate_id',
            'date_from', 'date_to', 'calls_count', 'leads_count', 'effective_calls',
            'effective_leads', 'non_trash_leads', 'approved_leads', 'buyout_count',
            'effective_rate', 'effective_percent', 'avg_duration', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


# Справочники
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class OfferSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Offer
        fields = ['id', 'external_id', 'name', 'category', 'category_name']


class OperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operator
        fields = ['id', 'username', 'name']


class AffiliateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Affiliate
        fields = ['id', 'external_id', 'name']


# Комбинированные сериализаторы для аналитики
class KPIAnalyticsSerializer(serializers.Serializer):
    """Сериализатор для KPI аналитики"""

    category_name = serializers.CharField()
    offer_id = serializers.IntegerField()
    offer_name = serializers.CharField()
    operator_name = serializers.CharField()
    aff_id = serializers.IntegerField()
    calls_count = serializers.IntegerField()
    total_duration = serializers.IntegerField()
    leads_count = serializers.IntegerField()
    buyout_count = serializers.IntegerField()
    total_container_leads = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    avg_call_duration = serializers.FloatField()
    buyout_rate = serializers.FloatField()

    class Meta:
        fields = '__all__'


class AdvancedKPIAnalysisSerializer(serializers.Serializer):
    """Сериализатор для расширенного анализа KPI"""

    type = serializers.CharField()
    key = serializers.CharField()
    description = serializers.CharField()
    kpi_stat = serializers.DictField()
    lead_container = serializers.DictField()
    recommendations = serializers.DictField()
    offers = serializers.ListField()
    operators = serializers.ListField()
    affiliates = serializers.ListField()

    class Meta:
        fields = '__all__'


class PivotConfigSerializer(serializers.Serializer):
    """Сериализатор для конфигурации сводных таблиц"""

    name = serializers.CharField()
    rows = serializers.ListField(child=serializers.CharField())
    columns = serializers.ListField(child=serializers.CharField())
    values = serializers.ListField(child=serializers.CharField())
    aggregation = serializers.CharField(default='SUM')
    filters = serializers.DictField(default=dict)

    class Meta:
        fields = '__all__'


class FormulaEvaluationSerializer(serializers.Serializer):
    """Сериализатор для оценки формул"""

    formula = serializers.CharField()
    sheet_data = serializers.DictField(default=dict)
    result = serializers.CharField(required=False)
    dependencies = serializers.ListField(required=False)
    error = serializers.CharField(required=False)

    class Meta:
        fields = ['formula', 'sheet_data', 'result', 'dependencies', 'error']