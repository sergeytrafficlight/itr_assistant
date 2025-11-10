# kpi_analyzer/admin.py
from django.contrib import admin
from .models import (
    Spreadsheet, Sheet, Cell, Formula, PivotTable,
    Category, Offer, Operator, Affiliate, KpiData  # ДОБАВЛЯЕМ KpiData
)

@admin.register(Spreadsheet)
class SpreadsheetAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name']

@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_display = ['name', 'spreadsheet', 'order']
    list_filter = ['spreadsheet']
    search_fields = ['name']

@admin.register(Cell)
class CellAdmin(admin.ModelAdmin):
    list_display = ['sheet', 'row', 'col', 'value']
    list_filter = ['sheet']
    search_fields = ['value']

@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display = ['name', 'formula_type', 'category']
    list_filter = ['formula_type', 'category']
    search_fields = ['name', 'formula_text']

@admin.register(PivotTable)
class PivotTableAdmin(admin.ModelAdmin):
    list_display = ['name', 'spreadsheet', 'created_at']
    list_filter = ['spreadsheet']
    search_fields = ['name']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['external_id', 'name', 'category']
    list_filter = ['category']
    search_fields = ['name', 'external_id']

@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ['username', 'name']
    search_fields = ['username', 'name']

@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = ['external_id', 'name']
    search_fields = ['external_id']

@admin.register(KpiData)
class KpiDataAdmin(admin.ModelAdmin):
    list_display = ['category', 'offer_name', 'operator_name', 'date_from', 'calls_count', 'leads_count']
    list_filter = ['category', 'date_from']
    search_fields = ['offer_name', 'operator_name']