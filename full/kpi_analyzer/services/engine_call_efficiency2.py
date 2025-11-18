import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from decimal import Decimal
from .statistics import safe_div

logger = logging.getLogger(__name__)

# Счетчик для ограничения логов
_log_counter = 0
_MAX_LOGS = 40


class Kpi:
    def __init__(self, r: Dict):
        self.id = r.get('call_eff_kpi_id')
        self.update_date = r.get('call_eff_plan_update_date')
        self.period_date = r.get('call_eff_period_date')
        self.offer_id = r.get('call_eff_offer_id')
        self.affiliate_id = r.get('call_eff_affiliate_id')
        self.confirmation_price = r.get('call_eff_confirmation_price') or 0.0
        self.buyout_price = r.get('call_eff_buyout_price') or 0.0
        self.operator_efficiency = r.get('call_eff_operator_efficiency') or 0.0
        self.operator_efficiency_update_date = r.get('call_eff_operator_efficiency_update_date')
        self.planned_approve = r.get('call_eff_planned_approve') or 0.0
        self.planned_approve_update_date = r.get('call_eff_approve_update_date')
        self.planned_buyout = r.get('call_eff_planned_buyout') or 0.0
        self.planned_buyout_update_date = r.get('call_eff_buyout_update_date')
        self.confirmation_price = r.get('call_eff_confirmation_price') or 0.0
        self.confirmation_price_update_date = r.get('call_eff_confirmation_price_update_date')
        self.buyout_price = r.get('call_eff_buyout_price') or 0.0
        self.buyout_price_update_date = r.get('call_eff_buyout_price_update_date')
        self.key_aff_offer = self._make_key(self.affiliate_id, self.offer_id)
        self.is_personal_plan = self.affiliate_id is not None

        # Исправленная проверка даты
        if self.period_date:
            if isinstance(self.period_date, str):
                if len(self.period_date) != 10:
                    raise ValueError(f"Wrong date for KPI '{self.period_date}' len({len(self.period_date)})")
            elif isinstance(self.period_date, (datetime, date)):
                # Конвертируем datetime в строку для единообразия
                self.period_date = self.period_date.strftime('%Y-%m-%d')
            else:
                raise ValueError(f"Unexpected type for period_date: {type(self.period_date)}")

    @staticmethod
    def _make_key(affiliate_id: Optional[str], offer_id: str) -> str:
        if affiliate_id is None:
            return str(offer_id)
        return f"{affiliate_id}-{offer_id}"

    @staticmethod
    def _make_key_cache(affiliate_id: Optional[str], offer_id: str, date: str) -> str:
        affiliate_str = affiliate_id if affiliate_id is not None else "null"
        return f"{affiliate_str}-{offer_id}-{date}"

    def print(self) -> str:
        return f"ID: {self.id} date: {self.period_date} offer_id: {self.offer_id} affiliate_id: {self.affiliate_id} op_eff: {self.operator_efficiency}"


class Call:
    def __init__(self, r: Dict):
        self.id = r.get('call_eff_id')
        self.crm_id = r.get('call_eff_crm_id')
        self.offer_id = r.get('call_eff_offer_id')
        self.uniqueid = r.get('call_eff_uniqueid')
        self.billsec = r.get('call_eff_billsec') or 0
        self.billsec_exact = r.get('call_eff_billsec_exact')
        if self.billsec_exact is not None:
            try:
                self.billsec_exact = int(self.billsec_exact)
                if self.billsec_exact < 0:
                    self.billsec_exact = self.billsec
            except (ValueError, TypeError):
                self.billsec_exact = self.billsec
        if self.billsec_exact and self.billsec_exact < self.billsec:
            self.billsec = self.billsec_exact
        self.operator_id = r.get('call_eff_operator_id')
        self.crm_lead_id = r.get('call_eff_crm_lead_id')
        self.calldate_str = r.get('call_eff_calldate')
        self.affiliate_id = r.get('call_eff_affiliate_id')
        self.calldate_date_str = self.calldate_str[:10] if self.calldate_str else ""
        if self.billsec is None:
            raise ValueError(f"Billsec is null id: {self.id}")

    def make_key(self) -> str:
        return f"{self.calldate_date_str} {self.operator_id} {self.crm_lead_id}"

    def print(self) -> str:
        return f"ID: {self.id} crm id: {self.crm_id} offer_id: {self.offer_id} affiliate_id: {self.affiliate_id} calldate: {self.calldate_str}"


class Lead:
    def __init__(self, r: Dict):
        self.crm_lead_id = r.get('call_eff_crm_lead_id')
        self.approved_at = r.get('call_eff_approved_at') or ''
        self.canceled_at = r.get('call_eff_canceled_at') or ''
        self.status_verbose = r.get('call_eff_status_verbose') or ''
        self.status_group = r.get('call_eff_status_group') or ''
        self.operator_id = r.get('call_eff_operator_id')
        self.is_salary_pay = True
        self.is_salary_not_pay_reason = ""
        self.offer_id =r.get('offer_id')
        if not self.offer_id:
            self.offer_id = r.get('call_eff_offer_id')
        if not self.offer_id:
            raise ValueError(f"Can't find offer id for lead crm id: {self.crm_lead_id}")

    def set_no_salary(self, reason: str):
        self.is_salary_pay = False
        self.is_salary_not_pay_reason = reason

    def finalize(self, is_fake_approve_func):
        self.is_salary_not_pay_reason = is_fake_approve_func(self.__dict__)
        self.is_salary_pay = (self.is_salary_not_pay_reason == "")


class CallGroup:
    def __init__(self, key: str, c: Call, efficiency_seconds: int):
        self.key = key
        self.calls = {}
        self.calls_effective = {}
        self.call_effective_first = None
        self.is_effective = False
        self.calls_effective_count = 0
        self.offer_id = c.offer_id
        self.affiliate_id = c.affiliate_id
        self.calldate_str = c.calldate_str
        self.efficiency_seconds = efficiency_seconds

    def push_call(self, call: Call):
        if call.uniqueid in self.calls:
            self.calls[call.uniqueid].billsec = max(self.calls[call.uniqueid].billsec, call.billsec)
        else:
            self.calls[call.uniqueid] = call

    def finalize(self):
        for call in self.calls.values():
            if call.billsec >= self.efficiency_seconds:
                self.calls_effective[call.uniqueid] = call
                self.calls_effective_count += 1
                if self.call_effective_first is None:
                    self.call_effective_first = call
        self.is_effective = bool(self.calls_effective_count)


class KpiList:
    min_eff = 0.1

    def __init__(self):
        self.kpi_by_aff_offer = {}
        self.kpi_by_offer = {}
        self.kpi_cache = {}

    def _push_kpi_item(self, l: Dict, kpi: Kpi, key: str):
        if key not in l:
            l[key] = []
        items = l[key]
        current_period_date = self._normalize_date(kpi.period_date)
        if items:
            last_period_date = self._normalize_date(items[-1].period_date)
            if last_period_date and current_period_date and last_period_date > current_period_date:
                raise ValueError(f"Wrong kpi sort order\nprev: {items[-1].print()}\nnew: {kpi.print()}")
        items.append(kpi)

    def _normalize_date(self, date_value):
        """Конвертирует дату в datetime объект для сравнения"""
        if date_value is None:
            return None
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, date):
            return datetime.combine(date_value, datetime.min.time())
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d')
            except ValueError:
                try:
                    return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return None
        return None

    def push_kpi(self, r: Dict):
        kpi = Kpi(r)
        if kpi.affiliate_id is not None:
            self._push_kpi_item(self.kpi_by_aff_offer, kpi, kpi.key_aff_offer)
        else:
            self._push_kpi_item(self.kpi_by_offer, kpi, str(kpi.offer_id))

    def _find_kpi_by_list(self, l: Dict, key: str, period_date: str) -> Optional[Kpi]:
        if key not in l:
            return None
        items = l[key]
        # Конвертируем переданную дату для сравнения
        normalized_period_date = self._normalize_date(period_date)
        if normalized_period_date is None:
            return None
        for i in range(len(items) - 1, -1, -1):
            # Конвертируем дату KPI для сравнения
            kpi_date = self._normalize_date(items[i].period_date)
            if kpi_date is None:
                continue
            if kpi_date > normalized_period_date:
                continue
            return items[i]
        return None

    def find_kpi(self, affiliate_id: Optional[str], offer_id: str, period_date: str) -> Optional[Kpi]:
        if isinstance(period_date, (datetime, date)):
            period_date = period_date.strftime('%Y-%m-%d')

        if len(period_date) != 10:
            raise ValueError(f"Wrong kpi request period date '{period_date}' expecting len 10")

        if affiliate_id is not None:
            key_cache = Kpi._make_key_cache(affiliate_id, offer_id, period_date)
            if key_cache in self.kpi_cache:
                return self.kpi_cache[key_cache]
            key = Kpi._make_key(affiliate_id, offer_id)
            kpi = self._find_kpi_by_list(self.kpi_by_aff_offer, key, period_date)
            if kpi:
                self.kpi_cache[key_cache] = kpi
                return kpi
        key_cache = Kpi._make_key_cache(None, offer_id, period_date)
        if key_cache in self.kpi_cache:
            return self.kpi_cache[key_cache]
        key = Kpi._make_key(None, offer_id)
        kpi = self._find_kpi_by_list(self.kpi_by_offer, key, period_date)
        if kpi:
            self.kpi_cache[key_cache] = kpi
            return kpi

    def find_kpi_operator_eff(self, affiliate_id: Optional[str], offer_id: str, period_date: str) -> Optional[Kpi]:
        kpi = self.find_kpi(affiliate_id, offer_id, period_date)
        if kpi is None:
            return None
        if (kpi.operator_efficiency is None or kpi.operator_efficiency < self.min_eff) and (
                kpi.affiliate_id == affiliate_id):
            return self.find_kpi(None, offer_id, period_date)
        else:
            return kpi


class Stat:
    def __init__(self):
        self.calls_group = {}
        self.leads = {}
        self.calls_group_effective_count = 0
        self.calls_group_with_calculation = 0
        self.calls_group_without_calculation = 0
        self.leads_effective_count = 0
        self.leads_with_calculation = 0
        self.leads_without_calculation = 0
        self.effective_rate = 0.0
        self.expecting_approved_leads = 0.0
        self.expecting_effective_rate = 0.0
        self.effective_percent = 0.0
        self.kpi_calculation_errors = ""
        self.call_efficiency_second = 60
        self.finalized = False

    def push_call(self, r: Dict):
        try:
            call = Call(r)
            key = call.make_key()
            if key not in self.calls_group:
                self.calls_group[key] = CallGroup(key, call, self.call_efficiency_second)
            self.calls_group[key].push_call(call)
        except Exception as e:
            logger.warning(f"Skip call: {e}")

    def push_lead(self, r: Dict):
        try:
            lead = Lead(r)
            if lead.crm_lead_id in self.leads:
                raise ValueError(f"Lead duplicate id: {lead.crm_lead_id}")
            self.leads[lead.crm_lead_id] = lead
        except Exception as e:
            logger.warning(f"Skip lead: {e}")

    def finalize(self, kpi_list: KpiList, is_fake_approve_func):
        global _log_counter
        if self.finalized:
            if _log_counter < _MAX_LOGS:
                logger.warning("Finalize called on already finalized Stat, skipping")
            return
        self.finalized = True

        for group in self.calls_group.values():
            group.finalize()

        for group in self.calls_group.values():
            if group.is_effective:
                if not group.offer_id:
                    self.calls_group_without_calculation += 1
                    continue

                self.calls_group_with_calculation += 1
                kpi = kpi_list.find_kpi_operator_eff(group.affiliate_id, str(group.offer_id), group.calldate_str)

                if kpi is None:
                    self.expecting_approved_leads = None
                    self.kpi_calculation_errors += f"Can't find KPI for offer: {group.offer_id} affiliate_id: {group.affiliate_id}\n"
                elif kpi.operator_efficiency < KpiList.min_eff:
                    self.expecting_approved_leads = None
                    self.kpi_calculation_errors += f"Wrong KPI for offer: {group.offer_id} affiliate_id: {group.affiliate_id} efficiency: {kpi.operator_efficiency} (< {KpiList.min_eff})\n"
                elif self.expecting_approved_leads is not None:
                    efficiency_value = float(kpi.operator_efficiency)
                    self.expecting_approved_leads += 1.0 / efficiency_value
        for lead in self.leads.values():
            lead.finalize(is_fake_approve_func)
            if lead.is_salary_pay:
                if not lead.offer_id:
                    self.leads_without_calculation += 1
                    continue
                self.leads_with_calculation += 1

        # 4. Расчет итоговых показателей (ТОЧНОЕ СООТВЕТСТВИЕ ЭТАЛОНУ)
        self.calls_group_effective_count = self.calls_group_without_calculation + self.calls_group_with_calculation
        self.leads_effective_count = self.leads_without_calculation + self.leads_with_calculation

        if self.calls_group_with_calculation and self.leads_with_calculation:
            self.effective_rate = safe_div(self.calls_group_with_calculation, self.leads_with_calculation)
        else:
            self.effective_rate = 0.0


        if self.expecting_approved_leads is not None:
            self.effective_percent = safe_div(self.leads_with_calculation, self.expecting_approved_leads) * 100
            self.expecting_effective_rate = safe_div(self.calls_group_with_calculation, self.expecting_approved_leads)
        else:
            self.effective_percent = None
            self.expecting_effective_rate = None

        # 6. Логирование
        if _log_counter < _MAX_LOGS:
            effective_percent_str = f"{self.effective_percent:.1f}%" if self.effective_percent is not None else "None"
            logger.info(
                f"Engine stat finalized: calls={self.calls_group_effective_count}, leads={self.leads_effective_count}, "
                f"effective_rate={self.effective_rate:.3f}, effective_percent={effective_percent_str}")
            _log_counter += 1
        elif _log_counter == _MAX_LOGS:
            logger.info(f"Достигнут лимит логов ({_MAX_LOGS}). Дальнейшие логи finalize подавляются.")
            _log_counter += 1


def push_call_to_engine(sql_data: Dict, stat: Stat):
    stat.push_call(sql_data)


def push_lead_to_engine(sql_data: Dict, offer_id: int, stat: Stat):
    sql_data = sql_data.copy()
    if offer_id is not None:
        sql_data['offer_id'] = offer_id
    stat.push_lead(sql_data)


def finalize_engine_stat(stat: Stat, kpi_list: KpiList):
    global _log_counter
    from .db_service import DBService

    def is_fake_approve_func(lead_dict: Dict) -> str:
        return DBService.is_fake_approve(lead_dict)

    if not stat.finalized:
        stat.finalize(kpi_list, is_fake_approve_func)
    else:
        if _log_counter < _MAX_LOGS:
            logger.warning("Engine stat already finalized, skipping")
            _log_counter += 1