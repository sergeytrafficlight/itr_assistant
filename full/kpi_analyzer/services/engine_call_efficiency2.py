from datetime import datetime, date
from typing import Dict, Optional, List, Any
import logging

from .engine_leads_processing import EngineLeadsProcessing
from .statistics import safe_div

logger = logging.getLogger(__name__)


class EngineCallEfficiency2:
    min_eff = 0.1
    call_efficiency_second = 60
    # УБРАЛИ KPI_MIN_DATE — теперь все даты разрешены
    # KPI_MIN_DATE = '2023-01-01'  # УДАЛЕНО

    class Kpi:
        def __init__(self, sql_data: Dict):
            self.id = sql_data.get('call_eff_kpi_id')
            self.update_date = sql_data.get('call_eff_plan_update_date')

            # Парсинг даты периода
            period_date = sql_data.get('call_eff_period_date')
            if period_date:
                if isinstance(period_date, (datetime, date)):
                    self.period_date = period_date.strftime('%Y-%m-%d')
                else:
                    raw = str(period_date).strip()
                    try:
                        dt = datetime.strptime(raw[:10], '%Y-%m-%d')
                        self.period_date = dt.strftime('%Y-%m-%d')
                    except Exception:
                        logger.warning(f"[KPI DATE ERROR] Invalid date: {raw}")
                        self.period_date = '1970-01-01'
            else:
                self.period_date = '1970-01-01'

            self.offer_id = sql_data.get('call_eff_offer_id')
            self.affiliate_id = sql_data.get('call_eff_affiliate_id')  # Исправлено: было call_pat_affiliate_id
            self.confirmation_price = sql_data.get('call_eff_confirmation_price')
            self.buyout_price = sql_data.get('call_eff_buyout_price')
            self.operator_efficiency = sql_data.get('call_eff_operator_efficiency')
            self.operator_efficiency_update_date = sql_data.get('call_eff_operator_efficiency_update_date')
            self.planned_approve = sql_data.get('call_eff_planned_approve')  # Исправлено: было call Eff
            self.planned_approve_update_date = sql_data.get('call_eff_approve_update_date')
            self.planned_buyout = sql_data.get('call_eff_planned_buyout')
            self.planned_buyout_update_date = sql_data.get('call_eff_buyout_update_date')
            self.confirmation_price_update_date = sql_data.get('call_eff_confirmation_price_update_date')
            self.buyout_price_update_date = sql_data.get('call_eff_buyout_price_update_date')

            self.key_aff_offer = EngineCallEfficiency2.kpi_make_key(self.affiliate_id, self.offer_id)
            self.is_personal_plan = self.affiliate_id is not None

        def print_kpi(self) -> str:
            return (
                f"ID: {self.id} date: {self.period_date} offer_id: {self.offer_id} "
                f"affiliate_id: {self.affiliate_id} op_eff: {self.operator_efficiency}"
            )

    class Call:
        def __init__(self, r: Dict):
            self.id = r.get('call_eff_id')
            self.crm_id = r.get('call_eff_crm_id')
            offer_id_raw = r.get('call_eff_offer_id')
            self.offer_id = int(offer_id_raw) if offer_id_raw and str(offer_id_raw).isdigit() else None
            self.uniqueid = r.get('call_eff_uniqueid')
            self.billsec = r.get('call_eff_billsec')
            self.billsec_exact = r.get('call_eff_billsec_exact')

            if self.billsec_exact is not None:
                try:
                    self.billsec_exact = int(self.billsec_exact)
                    if self.billsec_exact < 0:
                        self.billsec_exact = self.billsec
                except (ValueError, TypeError):
                    self.billsec_exact = self.billsec

            self.operator_id = r.get('call_eff_operator_id')
            self.crm_lead_id = r.get('call_eff_crm_lead_id')
            raw_calldate = r.get('call_eff_calldate', '')
            self.calldate_str = raw_calldate[:10] if raw_calldate else ''
            aff_id_raw = r.get('call_eff_affiliate_id')
            self.affiliate_id = int(aff_id_raw) if aff_id_raw and str(aff_id_raw).isdigit() else None

            if self.billsec is None:
                raise Exception(f"Billsec is null id: {self.id}")

            if self.billsec_exact is not None and self.billsec_exact < self.billsec:
                self.billsec = self.billsec_exact

            self.calldate_date_str = self.calldate_str

        def make_key(self) -> str:
            return f"{self.calldate_date_str} {self.operator_id} {self.crm_lead_id}"

    class Lead:
        def __init__(self, r: Dict, offer_id: int = None):
            self.crm_lead_id = r.get('call_eff_crm_lead_id')
            self.approved_at = r.get('call_eff_approved_at')
            self.canceled_at = r.get('call_eff_canceled_at')
            self.status_verbose = r.get('call_eff_status_verbose')
            self.status_group = r.get('call_eff_status_group')
            self.operator_id = r.get('call_eff_operator_id')
            self.offer_id = offer_id
            self.is_salary_pay = True
            self.is_salary_not_pay_reason = ""

        def finalize(self):
            self.is_salary_not_pay_reason = EngineLeadsProcessing.is_fake_approve({
                'status_verbose': self.status_verbose,
                'status_group': self.status_group,
                'approved_at': self.approved_at,
                'canceled_at': self.canceled_at
            })
            self.is_salary_pay = not bool(self.is_salary_not_pay_reason)

    class CallGroup:
        def __init__(self, key: str, call: 'EngineCallEfficiency2.Call', efficiency_call_seconds: int):
            self.key = key
            self.calls: Dict[str, 'EngineCallEfficiency2.Call'] = {}
            self.calls_effective: Dict[str, 'EngineCallEfficiency2.Call'] = {}
            self.call_effective_first: Optional['EngineCallEfficiency2.Call'] = None
            self.is_effective = False
            self.calls_effective_count = 0
            self.offer_id = call.offer_id
            self.affiliate_id = call.affiliate_id
            self.calldate_str = call.calldate_str
            self.efficiency_call_seconds = efficiency_call_seconds

        def push_call(self, call: 'EngineCallEfficiency2.Call'):
            if call.uniqueid in self.calls:
                self.calls[call.uniqueid].billsec = max(
                    self.calls[call.uniqueid].billsec, call.billsec
                )
            else:
                self.calls[call.uniqueid] = call

        def finalize(self):
            for call in self.calls.values():
                if call.billsec >= self.efficiency_call_seconds:
                    self.calls_effective[call.uniqueid] = call
                    self.calls_effective_count += 1
                    if self.call_effective_first is None:
                        self.call_effective_first = call
            self.is_effective = self.calls_effective_count > 0

    class KpiList:
        def __init__(self):
            self.kpi_by_aff_offer: Dict[str, List['EngineCallEfficiency2.Kpi']] = {}
            self.kpi_by_offer: Dict[str, List['EngineCallEfficiency2.Kpi']] = {}
            self.kpi_cache: Dict[str, 'EngineCallEfficiency2.Kpi'] = {}

        def push_kpi(self, sql_data: Dict):
            kpi = EngineCallEfficiency2.Kpi(sql_data)

            # УБРАЛИ ЖЁСТКИЙ СКИП ПО KPI_MIN_DATE
            # if kpi.period_date < EngineCallEfficiency2.KPI_MIN_DATE:
            #     logger.debug(f"[KPI SKIPPED] Too old: {kpi.print_kpi()}")
            #     return

            if kpi.affiliate_id is not None:
                key = kpi.key_aff_offer
                if key not in self.kpi_by_aff_offer:
                    self.kpi_by_aff_offer[key] = []
                if (self.kpi_by_aff_offer[key] and
                        self.kpi_by_aff_offer[key][-1].period_date > kpi.period_date):
                    raise Exception("Wrong kpi sort order")
                self.kpi_by_aff_offer[key].append(kpi)
            else:
                key = str(kpi.offer_id)
                if key not in self.kpi_by_offer:
                    self.kpi_by_offer[key] = []
                if (self.kpi_by_offer[key] and
                        self.kpi_by_offer[key][-1].period_date > kpi.period_date):
                    raise Exception("Wrong kpi sort order")
                self.kpi_by_offer[key].append(kpi)

        def find_kpi(self, affiliate_id: Optional[Any], offer_id: str, period_date) -> Optional['EngineCallEfficiency2.Kpi']:
            if isinstance(period_date, (datetime, date)):
                period_date_str = period_date.strftime('%Y-%m-%d')
            else:
                period_date_str = str(period_date)[:10]
            if len(period_date_str) != 10:
                return None

            key_cache = EngineCallEfficiency2.kpi_make_key_cache(affiliate_id, offer_id, period_date_str)
            if key_cache in self.kpi_cache:
                return self.kpi_cache[key_cache]

            storage = self.kpi_by_aff_offer if affiliate_id else self.kpi_by_offer
            key = EngineCallEfficiency2.kpi_make_key(affiliate_id, offer_id)
            if key not in storage:
                self.kpi_cache[key_cache] = None
                return None

            best_kpi = None
            for kpi in reversed(storage[key]):
                if kpi.period_date > period_date_str:
                    continue
                # УБРАЛИ KPI_MIN_DATE
                # if kpi.period_date < EngineCallEfficiency2.KPI_MIN_DATE:
                #     continue
                if (kpi.operator_efficiency is None or kpi.operator_efficiency < EngineCallEfficiency2.min_eff):
                    continue
                if best_kpi is None or kpi.period_date > best_kpi.period_date:
                    best_kpi = kpi

            self.kpi_cache[key_cache] = best_kpi
            if not best_kpi:
                logger.warning(f"[KPI NOT FOUND] offer={offer_id}, aff={affiliate_id}, req_date={period_date_str}")
            return best_kpi

        def find_kpi_operator_eff(self, affiliate_id: Optional[Any], offer_id: str, period_date) -> Optional['EngineCallEfficiency2.Kpi']:
            result = self.find_kpi(affiliate_id, offer_id, period_date)
            if (result and (result.operator_efficiency is None or result.operator_efficiency < EngineCallEfficiency2.min_eff)
                    and result.affiliate_id == affiliate_id):
                return self.find_kpi(None, offer_id, period_date)
            return result

    class Stat:
        def __init__(self):
            self.calls_group: Dict[str, 'EngineCallEfficiency2.CallGroup'] = {}
            self.leads: Dict[int, 'EngineCallEfficiency2.Lead'] = {}
            self.calls_group_with_calculation = 0
            self.calls_group_without_calculation = 0
            self.leads_with_calculation = 0
            self.leads_without_calculation = 0
            self.expecting_approved_leads: Optional[float] = 0.0
            self.effective_percent: Optional[float] = 0.0
            self.kpi_calculation_errors = ""
            self.finalized = False

        def push_call(self, call_data: Dict):
            try:
                call = EngineCallEfficiency2.Call(call_data)
                key = call.make_key()
                if key not in self.calls_group:
                    self.calls_group[key] = EngineCallEfficiency2.CallGroup(
                        key, call, EngineCallEfficiency2.call_efficiency_second
                    )
                self.calls_group[key].push_call(call)
            except Exception as e:
                logger.error(f"[CALL ERROR] {e} | data: {call_data}")

        def push_lead(self, lead_data: Dict, offer_id: int = None):
            try:
                lead_id = lead_data.get('call_eff_crm_lead_id')
                if not lead_id:
                    return
                lead = EngineCallEfficiency2.Lead(lead_data, offer_id=offer_id)
                if lead.crm_lead_id in self.leads:
                    return
                self.leads[lead.crm_lead_id] = lead
            except Exception as e:
                logger.error(f"[LEAD ERROR] {e} | lead_data: {lead_data}")

        def finalize(self, kpi_list: 'EngineCallEfficiency2.KpiList'):
            if self.finalized:
                raise Exception("Already finalized")
            self.finalized = True

            logger.info(f"[FINALIZE] Start: groups={len(self.calls_group)}, leads={len(self.leads)}")

            for group in self.calls_group.values():
                group.finalize()
                if not group.is_effective:
                    continue
                if not group.offer_id:
                    self.calls_group_without_calculation += 1
                    continue

                self.calls_group_with_calculation += 1
                kpi = kpi_list.find_kpi_operator_eff(group.affiliate_id, group.offer_id, group.calldate_str)
                if kpi is None:
                    self.kpi_calculation_errors += f"KPI not found: offer={group.offer_id} (aff: {group.affiliate_id})\n"
                    continue
                if kpi.operator_efficiency < EngineCallEfficiency2.min_eff:
                    continue

                if self.expecting_approved_leads is not None:
                    self.expecting_approved_leads += group.calls_effective_count * kpi.operator_efficiency

            for lead in self.leads.values():
                lead.finalize()
                if not lead.is_salary_pay:
                    continue
                if not lead.offer_id:
                    self.leads_without_calculation += 1
                    continue
                self.leads_with_calculation += 1

            if self.expecting_approved_leads not in (None, 0):
                self.effective_percent = safe_div(self.leads_with_calculation, self.expecting_approved_leads) * 100
            else:
                self.effective_percent = 0.0

            logger.info(f"[RESULT] Efficiency: {self.leads_with_calculation} leads / "
                        f"{self.expecting_approved_leads:.1f} expected = {self.effective_percent:.1f}%")

    @staticmethod
    def kpi_make_key(affiliate_id: Optional[Any], offer_id: int) -> str:
        return str(offer_id) if affiliate_id is None else f"{affiliate_id}-{offer_id}"

    @staticmethod
    def kpi_make_key_cache(affiliate_id: Optional[Any], offer_id: int, date: str) -> str:
        affiliate_str = "" if affiliate_id is None else str(affiliate_id)
        return f"{affiliate_str}-{offer_id}-{date}"

    @staticmethod
    def push_lead_to_engine(sql_data: Dict, offer_id: Optional[int], kpi_stat: 'KpiStat'):
        if kpi_stat.stat:
            kpi_stat.stat.push_lead(sql_data, offer_id=offer_id)

    @staticmethod
    def push_call_to_engine(sql_data: Dict, kpi_stat: 'KpiStat'):
        if kpi_stat.stat:
            kpi_stat.stat.push_call(sql_data)

    @staticmethod
    def finalize_engine_stat(kpi_stat: 'KpiStat', kpi_list: 'KpiList'):
        if not kpi_stat.stat.finalized:
            kpi_stat.stat.finalize(kpi_list)
        kpi_stat.leads_effective_count = kpi_stat.stat.leads_with_calculation
        kpi_stat.calls_group_effective_count = kpi_stat.stat.calls_group_with_calculation
        kpi_stat.effective_rate = safe_div(
            kpi_stat.leads_effective_count, kpi_stat.calls_group_effective_count
        )
        kpi_stat.effective_percent = kpi_stat.effective_rate * 100

    @staticmethod
    def get_kpi_query():
        # УБРАЛИ WHERE period_date >= '2023-01-01'
        return """
        SELECT 
            offer_plan.id AS call_eff_kpi_id,
            offer_plan.update_date AS call_eff_plan_update_date,
            offer_plan.period_date AS call_eff_period_date,
            offer_plan.offer_id AS call_eff_offer_id,
            offer_plan.affiliate_id AS call_eff_affiliate_id,
            offer_plan.confirmation_price AS call_eff_confirmation_price,
            offer_plan.buyout_price AS call_eff_buyout_price,
            offer_plan.operator_efficiency AS call_eff_operator_efficiency,
            offer_plan.operator_efficiency_update_date AS call_eff_operator_efficiency_update_date,
            offer_plan.planned_approve AS call_eff_planned_approve,
            offer_plan.approve_update_date AS call_eff_approve_update_date,
            offer_plan.planned_buyout AS call_eff_planned_buyout,
            offer_plan.buyout_update_date AS call_eff_buyout_update_date,
            offer_plan.confirmation_price_update_date AS call_eff_confirmation_price_update_date,
            offer_plan.buyout_price_update_date AS call_eff_buyout_price_update_date
        FROM partners_tlofferplanneddataperiod AS offer_plan
        LEFT JOIN partners_affiliate aff ON aff.id = offer_plan.affiliate_id
        ORDER BY offer_plan.period_date ASC
        """