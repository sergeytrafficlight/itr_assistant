# kpi_analyzer/services/statistics.py
from django.db import models
import math


def safe_div(numerator, denominator, default=0.0):
    """Безопасное деление с обработкой нуля"""
    if denominator is None or denominator == 0:
        return default
    return numerator / denominator


class CallEfficiencyStat:
    """Аналог engine_call_effeciency2.stat()"""

    def __init__(self):
        self.calls_group_effective_count = 0
        self.leads_effective_count = 0
        self.effective_percent = 0.0
        self.effective_rate = 0.0
        self.expecting_effective_rate = 0.0
        self.calls_count = 0
        self.leads_count = 0

    def push_lead(self, sql_data):
        """Обработка данных лида"""
        self.leads_count += 1
        # Логика определения эффективного лида
        if self._is_effective_lead(sql_data):
            self.leads_effective_count += 1

    def push_call(self, sql_data):
        """Обработка данных звонка"""
        self.calls_count += 1
        # Логика определения эффективного звонка
        if self._is_effective_call(sql_data):
            self.calls_group_effective_count += 1

    def finalyze(self, kpi_list=None):
        """Финальные расчеты"""
        self.effective_percent = safe_div(self.leads_effective_count, self.calls_group_effective_count) * 100
        self.effective_rate = safe_div(self.calls_group_effective_count, self.leads_effective_count)

    def _is_effective_lead(self, lead_data):
        """Определение эффективного лида"""
        # Логика из оригинального кода
        return lead_data.get('approved_at') is not None

    def _is_effective_call(self, call_data):
        """Определение эффективного звонка"""
        # Звонки длительностью >= 30 секунд
        return call_data.get('billsec', 0) >= 30


class LeadContainerStat:
    """Аналог engine_lead_container.stat()"""

    def __init__(self):
        self.leads_non_trash_count = 0
        self.leads_approved_count = 0
        self.leads_buyout_count = 0
        self.total_leads = 0

    def push_lead(self, sql_data):
        """Обработка данных лида"""
        self.total_leads += 1

        # Логика определения не треша
        if not self._is_trash_lead(sql_data):
            self.leads_non_trash_count += 1

        # Логика аппрува
        if sql_data.get('approved_at'):
            self.leads_approved_count += 1

        # Логика выкупа
        if sql_data.get('buyout_at'):
            self.leads_buyout_count += 1

    def finalyze(self):
        """Финальные расчеты"""
        pass

    def _is_trash_lead(self, lead_data):
        """Определение треш-лида"""
        # Логика из оригинального кода
        return lead_data.get('status') in ['trash', 'spam']