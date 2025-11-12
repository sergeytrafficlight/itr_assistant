from django.db import models
import math
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def safe_div(numerator, denominator, default=0.0):
    """Безопасное деление с обработкой нуля - ТОЧНО КАК В ЭТАЛОНЕ"""
    if denominator is None or denominator == 0:
        return default

    def to_float(value):
        if isinstance(value, Decimal):
            return float(value)
        elif value is None:
            return 0.0
        return value

    num = to_float(numerator)
    den = to_float(denominator)
    return num / den


MINUTE_MLSEC = 60 * 1000


def parse_date_time(date_str):
    """ТОЧНАЯ КОПИЯ parse_date_time ИЗ ЭТАЛОНА"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except:
        return None


class CallEfficiencyStat:
    def __init__(self):
        self.calls_group = {}
        self.leads = {}
        self.calls_group_effective_count = 0
        self.calls_group_with_calculation = 0
        self.calls_group_without_calculation = 0
        self.leads_effective_count = 0
        self.leads_with_calculation = 0
        self.leads_without_calculation = 0
        self.effective_rate = 0
        self.expecting_approved_leads = 0.0
        self.expecting_effective_rate = 0.0
        self.effective_percent = 0.0
        self.kpi_calculation_errors = ""
        self.call_effeciency_second = 60
        self.finalyzed = False
        self.name = ""

    def push_call(self, call_data):
        logger.debug(f"CallEfficiencyStat.push_call received data with keys: {list(call_data.keys())}")
        call = self.Call(call_data)
        key = call.make_key()
        if key not in self.calls_group:
            self.calls_group[key] = self.CallGroup(key, call, self.call_effeciency_second)
        self.calls_group[key].push_call(call)

    def push_lead(self, lead_data):
        logger.debug(f"CallEfficiencyStat.push_lead received data with keys: {list(lead_data.keys())}")
        lead = self.Lead(lead_data)

        if lead.crm_lead_id is None or lead.crm_lead_id == '':
            logger.debug("Lead skipped - no crm_lead_id")
            return

        if lead.crm_lead_id in self.leads:
            logger.debug(f"Lead duplicate id: {lead.crm_lead_id}")
            return

        self.leads[lead.crm_lead_id] = lead
        logger.debug(f"Lead added: {lead.crm_lead_id}")

    def finalyze(self, kpi_list=None):
        if self.finalyzed:
            logger.debug(f"CallEfficiencyStat уже финализирован для {self.name}")
            return

        logger.debug(f"Начинаем финализацию CallEfficiencyStat для {self.name}")
        self.finalyzed = True

        logger.debug(f"Before finalize: calls_groups={len(self.calls_group)}, leads={len(self.leads)}")

        self.calls_group_effective_count = 0
        self.calls_group_with_calculation = 0
        self.calls_group_without_calculation = 0
        self.leads_effective_count = 0
        self.leads_with_calculation = 0
        self.leads_without_calculation = 0
        self.effective_rate = 0
        self.expecting_approved_leads = 0.0
        self.expecting_effective_rate = 0.0
        self.effective_percent = 0.0

        for group in self.calls_group.values():
            group.finalyze()
            if group.is_effective:
                if group.offer_id == 0:
                    self.calls_group_without_calculation += 1
                    continue

                self.calls_group_with_calculation += 1

                if kpi_list and hasattr(kpi_list, 'find_kpi_operator_eff'):
                    kpi = kpi_list.find_kpi_operator_eff(group.affiliate_id, group.offer_id, group.calldate_str)
                else:
                    kpi = None

                if kpi is None:
                    self.expecting_approved_leads = None
                    self.kpi_calculation_errors += f"Can't find KPI for offer: {group.offer_id} affiliate_id: {group.affiliate_id}\n"
                elif getattr(kpi, 'operator_efficiency', 0) < 0.1:
                    self.expecting_approved_leads = None
                    self.kpi_calculation_errors += f"Wrong KPI for offer: {group.offer_id} affiliate_id: {group.affiliate_id} effeciency: {getattr(kpi, 'operator_efficiency', 0)} (< 0.1)\n"
                elif self.expecting_approved_leads is not None:
                    kpi_efficiency = getattr(kpi, 'operator_efficiency', 1.0)
                    if isinstance(kpi_efficiency, Decimal):
                        kpi_efficiency = float(kpi_efficiency)
                    self.expecting_approved_leads += 1.0 / kpi_efficiency

        for lead in self.leads.values():
            if not hasattr(lead, 'finalyzed') or not lead.finalyzed:
                lead.finalyze()

            if lead.is_salary_pay:
                if lead.offer_id == 0:
                    self.leads_without_calculation += 1
                    continue
                self.leads_with_calculation += 1

        if self.calls_group_with_calculation and self.leads_with_calculation:
            self.effective_rate = safe_div(self.calls_group_with_calculation, self.leads_with_calculation)

        if self.expecting_approved_leads is not None:
            self.effective_percent = safe_div(self.leads_with_calculation, self.expecting_approved_leads) * 100
            self.expecting_effective_rate = safe_div(self.calls_group_with_calculation, self.expecting_approved_leads)
        else:
            self.effective_percent = 0.0
            self.expecting_effective_rate = 0.0

        self.calls_group_effective_count = self.calls_group_without_calculation + self.calls_group_with_calculation
        self.leads_effective_count = self.leads_with_calculation + self.leads_without_calculation

        logger.debug(
            f"CallEfficiencyStat финализирован: calls={self.calls_group_effective_count}, leads={self.leads_effective_count}, rate={self.effective_rate}")

    class Call:
        def __init__(self, r):
            self.id = r.get('call_eff_id') or r.get('id', 0)
            self.crm_id = r.get('call_eff_crm_id') or r.get('crm_id', 0)
            self.offer_id = r.get('call_eff_offer_id') or r.get('offer_id', 0) or 0
            self.uniqueid = r.get('call_eff_uniqueid') or r.get('uniqueid', '')
            self.billsec = r.get('call_eff_billsec') or r.get('billsec', 0) or 0
            self.billsec_exact = r.get('call_eff_billsec_exact') or r.get('billsec_exact')
            self.operator_id = r.get('call_eff_operator_id') or r.get('operator_id', '')
            self.crm_lead_id = r.get('call_eff_crm_lead_id') or r.get('crm_lead_id', '')
            self.calldate_str = r.get('call_eff_calldate') or r.get('calldate', '')
            self.affiliate_id = r.get('call_eff_affiliate_id') or r.get('aff_id', 0) or 0

            def convert_value(value):
                if isinstance(value, Decimal):
                    return float(value)
                return value

            self.billsec = convert_value(self.billsec)
            self.offer_id = convert_value(self.offer_id)
            self.affiliate_id = convert_value(self.affiliate_id)

            if self.billsec_exact:
                try:
                    self.billsec_exact = convert_value(self.billsec_exact)
                    if self.billsec_exact < 0:
                        self.billsec_exact = self.billsec
                except:
                    self.billsec_exact = self.billsec

            if self.billsec_exact and self.billsec_exact < self.billsec:
                self.billsec = self.billsec_exact

            self.calldate_date_str = self.calldate_str[:10] if self.calldate_str else ""

        def make_key(self):
            return f"{self.calldate_date_str} {self.operator_id} {self.crm_lead_id}"

    class Lead:
        def __init__(self, r):
            self.crm_lead_id = r.get('call_eff_crm_lead_id') or r.get('id') or 0
            self.approved_at = r.get('call_eff_approved_at') or r.get('approved_at')
            self.canceled_at = r.get('call_eff_canceled_at') or r.get('canceled_at')
            self.status_verbose = r.get('call_eff_status_verbose') or r.get('status_verbose', '')
            self.status_group = r.get('call_eff_status_group') or r.get('status_group', '')
            self.operator_id = r.get('call_eff_operator_id') or r.get('operator_id', 0)
            self.is_salary_pay = True
            self.is_salary_not_pay_reason = ""
            self.offer_id = r.get('offer_id', 0) or 0
            self.finalyzed = False

            if isinstance(self.offer_id, Decimal):
                self.offer_id = int(self.offer_id)

        def set_no_salary(self, reason):
            self.is_salary_pay = False
            self.is_salary_not_pay_reason = reason

        def finalyze(self):
            if self.finalyzed:
                return

            self.finalyzed = True
            try:
                from .engine_leads_proccesing import EngineLeadsProcessing
                self.is_salary_not_pay_reason = EngineLeadsProcessing.is_fake_approve({
                    'status_verbose': self.status_verbose,
                    'status_group': self.status_group,
                    'approved_at': self.approved_at,
                    'canceled_at': self.canceled_at
                })
                self.is_salary_pay = not bool(self.is_salary_not_pay_reason)
            except:
                self.is_salary_pay = True
                self.is_salary_not_pay_reason = ""

    class CallGroup:
        def __init__(self, key, call, effeciency_call_seconds):
            self.key = key
            self.calls = {}
            self.calls_effective = {}
            self.call_effective_first = None
            self.is_effective = False
            self.calls_effective_count = 0
            self.offer_id = call.offer_id
            self.affiliate_id = call.affiliate_id
            self.calldate_str = call.calldate_str
            self.effeciency_call_seconds = effeciency_call_seconds
            self.finalyzed = False

        def push_call(self, call):
            self.calls[call.uniqueid] = call

        def finalyze(self):
            if self.finalyzed:
                return

            self.finalyzed = True
            for call in self.calls.values():
                if call.billsec >= self.effeciency_call_seconds:
                    self.calls_effective[call.uniqueid] = call
                    self.calls_effective_count += 1
                    if self.call_effective_first is None:
                        self.call_effective_first = call
            self.is_effective = self.calls_effective_count > 0


class LeadContainerStat:
    """ПОЛНЫЙ АНАЛОГ engine_lead_container.stat() ИЗ ЭТАЛОНА"""

    def __init__(self):
        self.leads = {}
        self.leads_count = 0
        self.leads_non_trash_count = 0
        self.leads_fake_approved_count = 0
        self.leads_approved_count = 0
        self.leads_fake_buyout_count = 0
        self.leads_buyout_count = 0
        self.dense_calls_count = 0
        self.dense_calls_expected_count = 0.0
        self.dense_calls_achive_percent = 0.0
        self.first_reaction_min = 0.0
        self.unprocessed_count = 0
        self.finalyzed = False
        self.last_calldate_dt_str = None

    def push_lead(self, sql_data):
        lead = self.Lead(sql_data)

        if lead.crm_id is None or lead.crm_id == '':
            return

        if lead.crm_id in self.leads:
            raise Exception(f"Duplicate lead id: {lead.crm_id}")

        self.leads[lead.crm_id] = lead

    def push_call(self, sql_data):
        call = self.Call(sql_data)
        if self.last_calldate_dt_str is not None and call.calldate_dt_str < self.last_calldate_dt_str:
            raise Exception(
                f"Wrong sort order calls, prev dt: {self.last_calldate_dt_str} < new dt:{call.calldate_dt_str}")
        self.last_calldate_dt_str = call.calldate_dt_str

        if call.crm_lead_id in self.leads:
            self.leads[call.crm_lead_id].push_call(call)

    def finalyze(self):
        if self.finalyzed:
            logger.debug("LeadContainerStat уже финализирован")
            return

        logger.debug("Начинаем финализацию LeadContainerStat")
        self.finalyzed = True
        self.leads_count = len(self.leads)

        for lead in self.leads.values():
            if not hasattr(lead, 'finalyzed') or not lead.finalyzed:
                lead.finalyze()

            if lead.is_trash == 0:
                self.leads_non_trash_count += 1

            if lead.is_fake_approve:
                self.leads_fake_approved_count += 1
            if lead.is_approve:
                self.leads_approved_count += 1

            if lead.is_fake_buyout:
                self.leads_fake_buyout_count += 1
            if lead.is_buyout:
                self.leads_buyout_count += 1

            self.dense_calls_count += lead.dense_calls_count
            self.dense_calls_expected_count += lead.dense_calls_expected_count
            if lead.first_reaction_min is not None:
                self.first_reaction_min += lead.first_reaction_min

            if lead.unprocessed:
                self.unprocessed_count += 1

        self.dense_calls_achive_percent = safe_div(self.dense_calls_count, self.dense_calls_expected_count) * 100
        if self.leads_count > 0:
            self.first_reaction_min = safe_div(self.first_reaction_min, self.leads_count)
        else:
            self.first_reaction_min = 0.0

        logger.debug(
            f"LeadContainerStat финализирован: leads={self.leads_count}, non_trash={self.leads_non_trash_count}, approved={self.leads_approved_count}, buyout={self.leads_buyout_count}")

    class Lead:
        def __init__(self, sql):
            self.crm_id = sql.get('lead_container_crm_lead_id')
            self.created_at = sql.get('lead_container_created_at')
            self.approved_at = sql.get('lead_container_approved_at')
            self.canceled_at = sql.get('lead_container_canceled_at')
            self.buyout_at = sql.get('lead_container_buyout_at')
            self.status_verbose = sql.get('lead_container_status_verbose', '').lower()
            self.status_group = sql.get('lead_container_status_group', '').lower()

            raw_is_trash = sql.get('lead_container_is_trash', 0) or 0
            if isinstance(raw_is_trash, Decimal):
                self.is_trash = int(raw_is_trash)
            else:
                self.is_trash = raw_is_trash

            self.now_dt = parse_date_time(sql.get('lead_container_now'))
            self.lead_ttl_till_dt = parse_date_time(sql.get('lead_container_lead_ttl_till'))
            self.created_at_dt = parse_date_time(self.created_at)
            self.approved_at_dt = parse_date_time(self.approved_at)
            self.canceled_at_dt = parse_date_time(self.canceled_at)

            self.is_fake_approve = False
            self.is_fake_approve_reason = ''
            self.is_approve = False
            self.is_fake_buyout = False
            self.is_buyout = False
            self.dense_calls_count = 0
            self.dense_calls_expected_count = 0.0
            self.first_reaction_min = None
            self.unprocessed = None
            self.calls = []
            self.finalyzed = False

            self.check_dense_till_dt = self.lead_ttl_till_dt

            if (self.approved_at_dt is not None and
                    self.check_dense_till_dt is not None and
                    self.check_dense_till_dt > self.approved_at_dt):
                self.check_dense_till_dt = self.approved_at_dt
            elif (self.canceled_at_dt is not None and
                  self.check_dense_till_dt is not None and
                  self.check_dense_till_dt > self.canceled_at_dt):
                self.check_dense_till_dt = self.canceled_at_dt

            if (self.now_dt is not None and
                    self.check_dense_till_dt is not None and
                    self.now_dt < self.check_dense_till_dt):
                self.check_dense_till_dt = self.now_dt

        def push_call(self, call):
            self.calls.append(call)

        def finalyze(self):
            if self.finalyzed:
                return

            self.finalyzed = True
            if self.approved_at and self.approved_at != '':
                try:
                    from .engine_leads_proccesing import EngineLeadsProcessing
                    self.is_fake_approve_reason = EngineLeadsProcessing.is_fake_approve({
                        'status_verbose': self.status_verbose,
                        'status_group': self.status_group,
                        'approved_at': self.approved_at,
                        'canceled_at': self.canceled_at
                    })
                    if self.is_fake_approve_reason:
                        self.is_fake_approve = True
                    else:
                        self.is_approve = True
                        self.is_trash = 0
                except Exception as e:
                    logger.error(f"Ошибка при проверке аппрува лида {self.crm_id}: {str(e)}")
                    self.is_approve = True
                    self.is_trash = 0

            if self.buyout_at and self.buyout_at != '':
                self.is_buyout = True

            if self.created_at_dt and self.check_dense_till_dt:
                time_diff_ms = (self.check_dense_till_dt - self.created_at_dt).total_seconds() * 1000
                time_diff_float = float(time_diff_ms)

                self.first_reaction_min = time_diff_float / MINUTE_MLSEC
                self.dense_calls_expected_count = (time_diff_float / MINUTE_MLSEC) / 288.0

                if self.dense_calls_expected_count < 1:
                    self.dense_calls_expected_count = 1

            prev_call = None
            sorted_calls = sorted([c for c in self.calls if c.calldate_dt is not None],
                                  key=lambda x: x.calldate_dt)

            for call in sorted_calls:
                if prev_call is not None and prev_call.unique_id == call.unique_id:
                    continue

                if prev_call is None and self.created_at_dt and call.calldate_dt:
                    reaction_time_ms = (call.calldate_dt - self.created_at_dt).total_seconds() * 1000
                    reaction_time_float = float(reaction_time_ms)
                    reaction_time_min = reaction_time_float / MINUTE_MLSEC
                    if self.first_reaction_min is None:
                        self.first_reaction_min = reaction_time_min
                    else:
                        self.first_reaction_min = min(reaction_time_min, self.first_reaction_min)

                if (prev_call is None or
                        (call.calldate_dt and prev_call.calldate_dt and
                         (call.calldate_dt - prev_call.calldate_dt).total_seconds() * 1000 / MINUTE_MLSEC >= 120)):
                    self.dense_calls_count += 1
                    prev_call = call

            if self.dense_calls_count > self.dense_calls_expected_count:
                self.dense_calls_count = self.dense_calls_expected_count

            if self.dense_calls_count > 0:
                self.unprocessed = False
            else:
                processed = False
                if (self.approved_at_dt is not None and
                        self.check_dense_till_dt is not None and
                        self.approved_at_dt <= self.check_dense_till_dt):
                    processed = True
                elif (self.canceled_at_dt is not None and
                      self.check_dense_till_dt is not None and
                      self.canceled_at_dt <= self.check_dense_till_dt):
                    processed = True

                self.unprocessed = not processed

    class Call:
        def __init__(self, sql):
            self.id = sql.get('lead_container_call_id')
            self.unique_id = sql.get('lead_container_call_uniqueid')
            self.crm_lead_id = sql.get('lead_container_crm_lead_id')
            self.calldate_dt_str = sql.get('lead_container_calldate_dt')
            self.calldate_dt = parse_date_time(self.calldate_dt_str)


def print_float(value):
    if value is None:
        return ""
    try:
        if isinstance(value, Decimal):
            value = float(value)
        num = float(value)
        if num == int(num):
            return str(int(num))
        formatted = f"{num:.4f}"
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
        return formatted
    except (ValueError, TypeError):
        return str(value)


def print_percent(prefix, numerator, denominator, suffix):
    if denominator is None or denominator == 0:
        return ""
    num = float(numerator) if isinstance(numerator, Decimal) else numerator
    den = float(denominator) if isinstance(denominator, Decimal) else denominator
    percent = (num / den) * 100
    return f"{prefix}{percent:.2f}%{suffix}"


class AggregatedCallEfficiencyStat:
    def __init__(self):
        self.calls_data = []
        self.leads_data = []
        self.calls_group_effective_count = 0
        self.leads_effective_count = 0
        self.effective_rate = 0
        self.effective_percent = 0.0
        self.expecting_effective_rate = 0.0
        self.finalyzed = False

    def push_call(self, call_data):
        self.calls_data.append(call_data)

    def push_lead(self, lead_data):
        self.leads_data.append(lead_data)

    def finalyze(self, kpi_list=None):
        if self.finalyzed:
            return

        self.finalyzed = True

        total_calls = 0
        total_leads = 0

        for call in self.calls_data:
            calls_count = call.get('calls_count', 0)
            total_calls += calls_count

        for lead in self.leads_data:
            leads_count = lead.get('leads_count', 0)
            total_leads += leads_count

        self.calls_group_effective_count = total_calls
        self.leads_effective_count = total_leads

        if total_calls > 0:
            self.effective_rate = safe_div(total_leads, total_calls)
            self.effective_percent = self.effective_rate * 100
        else:
            self.effective_rate = 0
            self.effective_percent = 0

        self.expecting_effective_rate = self.effective_rate
class GlobalLeadContainerStat:
    def __init__(self):
        self.leads = {}
        self.calls = []
        self.raw_container_data = []
        self.leads_count = 0
        self.leads_non_trash_count = 0
        self.leads_fake_approved_count = 0
        self.leads_approved_count = 0
        self.leads_fake_buyout_count = 0
        self.leads_buyout_count = 0
        self.dense_calls_count = 0
        self.dense_calls_expected_count = 0.0
        self.dense_calls_achive_percent = 0.0
        self.first_reaction_min = 0.0
        self.unprocessed_count = 0
        self.finalyzed = False

    def push_lead(self, sql_data):
        self.raw_container_data.append(sql_data)
        lead = LeadContainerStat.Lead(sql_data)
        if lead.crm_id and lead.crm_id not in self.leads:
            self.leads[lead.crm_id] = lead

    def push_call(self, sql_data):
        call = LeadContainerStat.Call(sql_data)
        self.calls.append(call)

    def finalyze(self):
        if self.finalyzed:
            return
        self.finalyzed = True
        self.calls.sort(key=lambda x: x.calldate_dt_str or '')
        for call in self.calls:
            if call.crm_lead_id in self.leads:
                self.leads[call.crm_lead_id].push_call(call)
        for lead in self.leads.values():
            if not hasattr(lead, 'finalyzed') or not lead.finalyzed:
                lead.finalyze()
            if lead.is_trash == 0:
                self.leads_non_trash_count += 1
            if lead.is_fake_approve:
                self.leads_fake_approved_count += 1
            if lead.is_approve:
                self.leads_approved_count += 1
            if lead.is_fake_buyout:
                self.leads_fake_buyout_count += 1
            if lead.is_buyout:
                self.leads_buyout_count += 1
            self.dense_calls_count += lead.dense_calls_count
            self.dense_calls_expected_count += lead.dense_calls_expected_count
            if lead.first_reaction_min is not None:
                self.first_reaction_min += lead.first_reaction_min
            if lead.unprocessed:
                self.unprocessed_count += 1
        self.leads_count = len(self.leads)
        self.dense_calls_achive_percent = safe_div(self.dense_calls_count, self.dense_calls_expected_count) * 100
        if self.leads_count > 0:
            self.first_reaction_min = safe_div(self.first_reaction_min, self.leads_count)