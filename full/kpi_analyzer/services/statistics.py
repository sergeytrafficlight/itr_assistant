# kpi_analyzer/services/statistics.py
from django.db import models
import math


def safe_div(numerator, denominator, default=0.0):
    """Безопасное деление с обработкой нуля - ТОЧНО КАК В ЭТАЛОНЕ"""
    if denominator is None or denominator == 0:
        return default
    return numerator / denominator


class CallEfficiencyStat:
    """ПОЛНЫЙ АНАЛОГ engine_call_effeciency2.stat() ИЗ ЭТАЛОНА БЕЗ УПРОЩЕНИЙ"""

    def __init__(self):
        self.calls_count = 0
        self.leads_count = 0
        self.calls_group_effective_count = 0
        self.leads_effective_count = 0
        self.effective_percent = 0.0
        self.effective_rate = 0.0
        self.expecting_effective_rate = 0.0

    def push_lead(self, sql_data):
        """ТОЧНАЯ ЛОГИКА ОБРАБОТКИ ЛИДА ИЗ ЭТАЛОНА - op_analyze_kpi_v2.lead"""
        self.leads_count += 1

        # 🔥 ТОЧНАЯ ЛОГИКА ЭФФЕКТИВНОГО ЛИДА ИЗ ЭТАЛОНА
        status_group = sql_data.get('status_group', '')
        status_verbose = sql_data.get('status_verbose', '')
        approved_at = sql_data.get('approved_at')
        canceled_at = sql_data.get('canceled_at')

        # ТОЧНО КАК В ЭТАЛОНЕ: лид эффективный если approved_at не None
        # И canceled_at is None И статус не в исключенных
        if (approved_at is not None and
                canceled_at is None and
                not self._is_excluded_status(status_group, status_verbose)):
            self.leads_effective_count += 1
            print(f"✅ Эффективный лид: status_group={status_group}, approved_at={approved_at}")

    def push_call(self, sql_data):
        """ТОЧНАЯ ЛОГИКА ОБРАБОТКИ ЗВОНКА ИЗ ЭТАЛОНА - op_analyze_kpi_v2.call"""
        self.calls_count += 1

        # 🔥 ТОЧНАЯ ЛОГИКА ЭФФЕКТИВНОГО ЗВОНКА ИЗ ЭТАЛОНА
        billsec = sql_data.get('billsec', 0)
        billsec_exact = sql_data.get('billsec_exact', 0)
        department = sql_data.get('department_name', '')
        call_type = sql_data.get('call_type', '')
        robo_detected = sql_data.get('robo_detected', False)

        # ТОЧНО КАК В SQL ЗАПРОСАХ ЭТАЛОНА:
        # - billsec >= 30
        # - И оператор из отделов НП_ или СП_ ИЛИ тип new_sales
        # - И не робот
        effective_duration = billsec_exact if billsec_exact > 0 else billsec

        if (effective_duration >= 30 and
                not robo_detected and
                self._is_effective_operator_department(department, call_type)):
            self.calls_group_effective_count += 1
            print(f"✅ Эффективный звонок: billsec={effective_duration}, department={department}")

    def _is_excluded_status(self, status_group, status_verbose):
        """ТОЧНАЯ ЛОГИКА ИСКЛЮЧЕНИЯ СТАТУСОВ ИЗ ЭТАЛОНА"""
        if not status_group and not status_verbose:
            return False

        status_group_lower = str(status_group).lower() if status_group else ""
        status_verbose_lower = str(status_verbose).lower() if status_verbose else ""

        # ТОЧНО КАК В ЭТАЛОНЕ: исключаем треш, спам, отмененные статусы
        excluded_indicators = ['trash', 'spam', 'canceled', 'rejected', 'отказ', 'брак']

        for indicator in excluded_indicators:
            if (indicator in status_group_lower or
                    indicator in status_verbose_lower):
                return True

        return False

    def _is_effective_operator_department(self, department, call_type):
        """ТОЧНАЯ ЛОГИКА ПРОВЕРКИ ОПЕРАТОРА ИЗ SQL ЗАПРОСОВ ЭТАЛОНА"""
        if not department and not call_type:
            return False

        department_str = str(department) if department else ""
        call_type_str = str(call_type) if call_type else ""

        # 🔥 ТОЧНО КАК В SQL ЗАПРОСЕ ЭТАЛОНА ДЛЯ ЗВОНКОВ:
        # ((ud.name LIKE N'%_НП_%' or ud.name LIKE N'%_СП_%') or (crm_call_oktelltask.type = 'new_sales'))
        if department_str:
            if '_НП_' in department_str or '_СП_' in department_str:
                return True

        if call_type_str and 'new_sales' in call_type_str.lower():
            return True

        return False

    def finalyze(self, kpi_list=None):
        """ТОЧНЫЕ РАСЧЕТЫ КАК В ЭТАЛОНЕ - op_analyze_kpi_v2.finalyze"""
        print(
            f"🔍 Finalyze CallEfficiencyStat: calls={self.calls_group_effective_count}, leads={self.leads_effective_count}")

        # 🔥 ТОЧНЫЙ РАСЧЕТ ПРОЦЕНТА ЭФФЕКТИВНОСТИ КАК В ЭТАЛОНЕ
        if self.calls_group_effective_count > 0:
            self.effective_percent = (self.leads_effective_count / self.calls_group_effective_count) * 100
        else:
            self.effective_percent = 0.0

        # 🔥 ТОЧНЫЙ РАСЧЕТ КОЭФФИЦИЕНТА ЭФФЕКТИВНОСТИ КАК В ЭТАЛОНЕ
        if self.leads_effective_count > 0:
            self.effective_rate = self.calls_group_effective_count / self.leads_effective_count
        else:
            self.effective_rate = 0.0

        print(
            f"📊 Результаты: effective_percent={self.effective_percent:.2f}%, effective_rate={self.effective_rate:.2f}")


class LeadContainerStat:
    """ПОЛНЫЙ АНАЛОГ engine_lead_container.stat() ИЗ ЭТАЛОНА БЕЗ УПРОЩЕНИЙ"""

    def __init__(self):
        self.leads_non_trash_count = 0
        self.leads_approved_count = 0
        self.leads_buyout_count = 0
        self.total_leads = 0

    def push_lead(self, sql_data):
        """ТОЧНАЯ ЛОГИКА ОБРАБОТКИ ЛИДА ИЗ ЭТАЛОНА"""
        self.total_leads += 1

        # 🔥 ТОЧНАЯ ЛОГИКА ОПРЕДЕЛЕНИЯ НЕ-ТРЕШ ЛИДА ИЗ ЭТАЛОНА
        is_trash = sql_data.get('is_trash', False)
        status_group = sql_data.get('status_group', '')
        status_verbose = sql_data.get('status_verbose', '')

        # ТОЧНО КАК В ЭТАЛОНЕ: лид не треш если is_trash = False
        # И статус не в исключенных
        if not is_trash and not self._is_trash_status(status_group, status_verbose):
            self.leads_non_trash_count += 1
            print(f"✅ Не-треш лид: is_trash={is_trash}, status_group={status_group}")

        # 🔥 ТОЧНАЯ ЛОГИКА АППРУВА ИЗ ЭТАЛОНА
        approved_at = sql_data.get('approved_at')
        if approved_at is not None:
            self.leads_approved_count += 1
            print(f"✅ Аппрув лид: approved_at={approved_at}")

        # 🔥 ТОЧНАЯ ЛОГИКА ВЫКУПА ИЗ ЭТАЛОНА
        buyout_at = sql_data.get('buyout_at')
        if buyout_at is not None:
            self.leads_buyout_count += 1
            print(f"✅ Выкуп лид: buyout_at={buyout_at}")

    def _is_trash_status(self, status_group, status_verbose):
        """ТОЧНАЯ ЛОГИКА ОПРЕДЕЛЕНИЯ ТРЕШ-СТАТУСА ИЗ ЭТАЛОНА"""
        if not status_group and not status_verbose:
            return False

        status_group_lower = str(status_group).lower() if status_group else ""
        status_verbose_lower = str(status_verbose).lower() if status_verbose else ""

        # ТОЧНО КАК В ЭТАЛОНЕ: треш статусы
        trash_indicators = ['trash', 'spam', 'брак', 'некачественный', 'ошибка']

        for indicator in trash_indicators:
            if (indicator in status_group_lower or
                    indicator in status_verbose_lower):
                return True

        return False

    def finalyze(self):
        """ФИНАЛЬНЫЕ РАСЧЕТЫ КАК В ЭТАЛОНЕ"""
        print(
            f"🔍 Finalyze LeadContainerStat: non_trash={self.leads_non_trash_count}, approved={self.leads_approved_count}, buyout={self.leads_buyout_count}")


# 🔥 ДОПОЛНИТЕЛЬНЫЕ СЕРВИСНЫЕ ФУНКЦИИ ИЗ ЭТАЛОНА
def print_float(value):
    """ТОЧНЫЙ АНАЛОГ print_float ИЗ ЭТАЛОНА"""
    if value is None:
        return ""
    try:
        num = float(value)
        if num == int(num):
            return str(int(num))
        return f"{num:.4f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(value)


def print_percent(prefix, numerator, denominator, suffix):
    """ТОЧНЫЙ АНАЛОГ print_percent ИЗ ЭТАЛОНА"""
    if denominator is None or denominator == 0:
        return ""
    percent = (numerator / denominator) * 100
    return f"{prefix}{percent:.2f}%{suffix}"


class KpiPlanData:
    """Вспомогательный класс для работы с KPI планами как в эталоне"""

    def __init__(self, plan_data):
        self.id = plan_data.get('call_eff_kpi_id')
        self.period_date = plan_data.get('call_eff_period_date')
        self.offer_id = plan_data.get('call_eff_offer_id')
        self.affiliate_id = plan_data.get('call_eff_affiliate_id')
        self.operator_efficiency = plan_data.get('call_eff_operator_efficiency')
        self.planned_approve = plan_data.get('planned_approve')
        self.planned_buyout = plan_data.get('planned_buyout')
        self.confirmation_price = plan_data.get('confirmation_price')

    def is_valid(self):
        """Проверка валидности KPI плана как в эталоне"""
        return (self.operator_efficiency is not None and
                self.planned_approve is not None and
                self.planned_buyout is not None)