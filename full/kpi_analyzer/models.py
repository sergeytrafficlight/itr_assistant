# kpi_analyzer/models.py
from django.db import models

# === ЛОКАЛЬНЫЕ МОДЕЛИ (в default БД) ===
class Spreadsheet(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Sheet(models.Model):
    spreadsheet = models.ForeignKey(Spreadsheet, on_delete=models.CASCADE, related_name='sheets')
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.spreadsheet.name} - {self.name}"

class Cell(models.Model):
    sheet = models.ForeignKey(Sheet, on_delete=models.CASCADE, related_name='cells')
    row = models.IntegerField()
    col = models.IntegerField()
    value = models.TextField(blank=True, null=True)
    formula = models.TextField(blank=True, null=True)
    computed_value = models.TextField(blank=True, null=True)
    style = models.JSONField(default=dict, blank=True)
    dependency_list = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ('sheet', 'row', 'col')

    def __str__(self):
        return f"{self.sheet.name}: {self.get_cell_ref()}"

    def get_cell_ref(self):
        import string
        col_letter = ''
        col = self.col
        while col >= 0:
            col, remainder = divmod(col, 26)
            col_letter = string.ascii_uppercase[remainder] + col_letter
            col -= 1
        return f"{col_letter}{self.row + 1}"

class CellDependency(models.Model):
    cell = models.ForeignKey(Cell, on_delete=models.CASCADE, related_name='dependencies')
    depends_on = models.ForeignKey(Cell, on_delete=models.CASCADE, related_name='dependents')

    class Meta:
        unique_together = ('cell', 'depends_on')

class Formula(models.Model):
    name = models.CharField(max_length=100)
    formula_text = models.TextField()
    formula_type = models.CharField(max_length=50, default='custom')
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name

class PivotTable(models.Model):
    spreadsheet = models.ForeignKey(Spreadsheet, on_delete=models.CASCADE, related_name='pivot_tables')
    name = models.CharField(max_length=255)
    config = models.JSONField()
    data_range = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# === МОДЕЛИ ИЗ ВНЕШНЕЙ БД `itrade` (только чтение) ===
class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = 'partners_groupoffer'

    def __str__(self):
        return self.name

class Offer(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'partners_offer'

    def __str__(self):
        return self.name

class Operator(models.Model):
    username = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'partners_lvoperator'

    def __str__(self):
        return self.username

class Affiliate(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'partners_affiliate'

    def __str__(self):
        return f"{self.external_id}: {self.name}"

class KpiData(models.Model):
    """Модель для хранения агрегированных KPI данных для сводных таблиц"""
    category = models.CharField(max_length=255, blank=True, null=True)
    offer_name = models.CharField(max_length=255, blank=True, null=True)
    operator_name = models.CharField(max_length=255, blank=True, null=True)
    affiliate_id = models.IntegerField(blank=True, null=True)

    # Даты для фильтрации
    date_from = models.DateField(blank=True, null=True)
    date_to = models.DateField(blank=True, null=True)

    # Основные метрики
    calls_count = models.IntegerField(default=0)
    leads_count = models.IntegerField(default=0)
    effective_calls = models.IntegerField(default=0)
    effective_leads = models.IntegerField(default=0)
    non_trash_leads = models.IntegerField(default=0)
    approved_leads = models.IntegerField(default=0)
    buyout_count = models.IntegerField(default=0)

    # Расчетные показатели
    effective_rate = models.FloatField(default=0.0)
    effective_percent = models.FloatField(default=0.0)
    avg_duration = models.FloatField(default=0.0)

    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kpi_data'
        indexes = [
            models.Index(fields=['category', 'date_from']),
            models.Index(fields=['offer_name', 'operator_name']),
        ]

    def __str__(self):
        return f"{self.category} - {self.offer_name} - {self.date_from}"
