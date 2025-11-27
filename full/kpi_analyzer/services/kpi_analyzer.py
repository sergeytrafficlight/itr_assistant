from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import time
from types import SimpleNamespace

from .engine_call_efficiency2 import (
    KpiList, Stat as CallStat, push_lead_to_engine, push_call_to_engine,
    finalize_engine_stat
)
from .statistics import safe_div, safe_float
from .db_service import DBService

logger = logging.getLogger(__name__)


class Recommendation:
    def __init__(self, value, comment: str = ""):
        self.value = value
        self.comment = comment


class RecommendationEngine:
    def __init__(self, calls_count_for_analyze: int = 30):
        self.calls_count_for_analyze = calls_count_for_analyze

    def sort_operators_by_efficiency(self, operators: Dict[str, Any]) -> List[Any]:
        result1 = []
        result2 = []

        for operator in operators.values():
            if (operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze and
                    operator.kpi_stat.effective_rate > 0.0):
                result1.append(operator)
            else:
                result2.append(operator)

        result1.sort(key=lambda x: x.kpi_stat.effective_rate)
        return result1 + result2

    def get_operators_for_recommendations(self, operators: List[Any]) -> Recommendation:
        eff_operators = 0
        for operator in operators:
            if (operator.kpi_stat.effective_rate > 0.0 and
                    operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze):
                eff_operators += 1

        eff_operators_count = round(eff_operators * 0.4)

        if eff_operators_count < 3:
            return Recommendation(None, "Недостаточно операторов для расчета плана")

        if eff_operators_count > 5:
            eff_operators_count = 5

        result = []
        comment = f"Операторов для анализа всего: {eff_operators_count}\n"
        calls_total = 0
        leads_total = 0

        for i, operator in enumerate(operators):
            if len(result) >= eff_operators_count:
                break
            if (operator.kpi_stat.effective_rate > 0.0 and
                    operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze):
                result.append(operator.key)
                calls_total += operator.kpi_stat.calls_group_effective_count
                leads_total += operator.kpi_stat.leads_effective_count
                comment += f"{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"

        comment += f"Звонков: {calls_total} лидов: {leads_total}\n"
        comment += f"Результат: {safe_div(calls_total, leads_total)}\n"

        return Recommendation(result, comment)


class KpiStat:
    def __init__(self):
        self.calls_group_effective_count = 0
        self.leads_effective_count = 0
        self.effective_percent = 0.0
        self.effective_rate = 0.0
        self.expecting_effective_rate = 0.0
        self.stat = CallStat()


class CommonItem:
    def __init__(self, key: str, description: str):
        self.key = key
        self.description = description
        self.kpi_stat = KpiStat()
        self.kpi_current_plan: Optional[Any] = None
        self.recommended_efficiency: Recommendation = Recommendation(None, "")
        self.recommended_approve: Recommendation = Recommendation(None, "")
        self.recommended_buyout: Recommendation = Recommendation(None, "")
        self.recommended_confirmation_price: Recommendation = Recommendation(None, "")
        self.expecting_approve_leads: Optional[float] = None
        self.expecting_buyout_leads: Optional[float] = None

        self.kpi_eff_need_correction = False
        self.kpi_eff_need_correction_str = ""
        self.kpi_app_need_correction = False
        self.kpi_app_need_correction_str = ""
        self.kpi_buyout_need_correction = False
        self.kpi_buyout_need_correction_str = ""
        self.kpi_confirmation_price_need_correction = False
        self.kpi_confirmation_price_need_correction_str = ""

        self.lead_container = SimpleNamespace(
            leads_non_trash_count=0,
            leads_approved_count=0,
            leads_buyout_count=0,
            leads_trash_count=0,
            leads_total_count=0,
            leads_raw_count=0
        )
        self.approve_percent_fact: Optional[float] = None
        self.buyout_percent_fact: Optional[float] = None
        self.trash_percent: Optional[float] = None
        self.raw_to_approve_percent: Optional[float] = None
        self.raw_to_buyout_percent: Optional[float] = None
        self.non_trash_to_buyout_percent: Optional[float] = None

    def push_lead(self, sql_data: Dict, offer_id: int = None):
        push_lead_to_engine(sql_data, offer_id, self.kpi_stat.stat)

    def push_call(self, sql_data: Dict):
        push_call_to_engine(sql_data, self.kpi_stat.stat)

    def calculate_correction_flags(self):
        self.kpi_eff_need_correction = False
        self.kpi_eff_need_correction_str = ""
        self.kpi_app_need_correction = False
        self.kpi_app_need_correction_str = ""
        self.kpi_buyout_need_correction = False
        self.kpi_buyout_need_correction_str = ""

        if self.kpi_current_plan and self.recommended_efficiency.value:
            plan_eff = safe_float(self.kpi_current_plan.operator_efficiency) or 0
            rec_eff = safe_float(self.recommended_efficiency.value) or 0
            if plan_eff is not None and rec_eff is not None:
                if abs(plan_eff - rec_eff) > 0.2:
                    self.set_kpi_eff_need_correction(f"Эффективность: план {plan_eff:.1f}% vs рек. {rec_eff:.1f}%")
            elif plan_eff is None or plan_eff == 0:
                self.set_kpi_eff_need_correction("KPI эффективности не установлен")

        if self.lead_container.leads_non_trash_count >= 10:
            current_approve = self.approve_percent_fact or 0

            if current_approve < 20:
                self.set_kpi_app_need_correction(f"Критически низкий аппрув: {current_approve:.1f}%")
            elif current_approve < 30:
                self.set_kpi_app_need_correction(f"Низкий аппрув: {current_approve:.1f}%")

            if self.recommended_approve and self.recommended_approve.value:
                rec_approve = safe_float(self.recommended_approve.value) or 0
                if abs(current_approve - rec_approve) > 5:
                    self.set_kpi_app_need_correction(f"Аппрув: факт {current_approve:.1f}% vs рек. {rec_approve:.1f}%")

        if self.lead_container.leads_approved_count >= 5:
            current_buyout = self.buyout_percent_fact or 0

            if current_buyout < 15:
                self.set_kpi_buyout_need_correction(f"Критически низкий выкуп: {current_buyout:.1f}%")
            elif current_buyout < 25:
                self.set_kpi_buyout_need_correction(f"Низкий выкуп: {current_buyout:.1f}%")

            if self.recommended_buyout and self.recommended_buyout.value:
                rec_buyout = safe_float(self.recommended_buyout.value) or 0
                if abs(current_buyout - rec_buyout) > 5:
                    self.set_kpi_buyout_need_correction(f"Выкуп: факт {current_buyout:.1f}% vs рек. {rec_buyout:.1f}%")

        if self.lead_container.leads_total_count > 10:
            current_trash = self.trash_percent or 0
            if current_trash > 60:
                self.set_kpi_app_need_correction(f"Высокий процент треша: {current_trash:.1f}%")

    def finalize(self, kpi_list: KpiList):
        finalize_engine_stat(self.kpi_stat.stat, kpi_list)

        self.kpi_stat.calls_group_effective_count = self.kpi_stat.stat.calls_group_effective_count
        self.kpi_stat.leads_effective_count = self.kpi_stat.stat.leads_effective_count
        self.kpi_stat.effective_percent = self.kpi_stat.stat.effective_percent
        self.kpi_stat.effective_rate = self.kpi_stat.stat.effective_rate
        self.kpi_stat.expecting_effective_rate = self.kpi_stat.stat.expecting_effective_rate

        lc = self.lead_container

        if lc.leads_non_trash_count > 0:
            self.approve_percent_fact = safe_div(
                lc.leads_approved_count,
                lc.leads_non_trash_count
            ) * 100

        if lc.leads_approved_count > 0:
            self.buyout_percent_fact = safe_div(
                lc.leads_buyout_count,
                lc.leads_approved_count
            ) * 100

        if lc.leads_total_count > 0:
            self.trash_percent = safe_div(
                lc.leads_trash_count,
                lc.leads_total_count
            ) * 100

        if lc.leads_raw_count > 0:
            self.raw_to_approve_percent = safe_div(
                lc.leads_approved_count,
                lc.leads_raw_count
            ) * 100

        if lc.leads_raw_count > 0:
            self.raw_to_buyout_percent = safe_div(
                lc.leads_buyout_count,
                lc.leads_raw_count
            ) * 100

        if lc.leads_non_trash_count > 0:
            self.non_trash_to_buyout_percent = safe_div(
                lc.leads_buyout_count,
                lc.leads_non_trash_count
            ) * 100

        if self.kpi_current_plan is not None:
            self.expecting_approve_leads = safe_float(
                lc.leads_non_trash_count * self.kpi_current_plan.planned_approve)
            self.expecting_buyout_leads = safe_float(
                lc.leads_approved_count * self.kpi_current_plan.planned_buyout)

        self.calculate_correction_flags()

    def set_kpi_eff_need_correction(self, comment: str):
        self.kpi_eff_need_correction = True
        self.kpi_eff_need_correction_str = comment

    def set_kpi_app_need_correction(self, comment: str):
        self.kpi_app_need_correction = True
        self.kpi_app_need_correction_str = comment

    def set_kpi_buyout_need_correction(self, comment: str):
        self.kpi_buyout_need_correction = True
        self.kpi_buyout_need_correction_str = comment

    def set_confirmation_price_need_correction(self, comment: str):
        self.kpi_confirmation_price_need_correction = True
        self.kpi_confirmation_price_need_correction_str = comment


class OfferItem(CommonItem):
    def __init__(self, key: str, description: str):
        super().__init__(key, description)


class CategoryItem:
    def __init__(self, key: str, name: str):
        self.key = key
        self.description = name
        self.offer: Dict[str, OfferItem] = {}
        self.aff: Dict[str, CommonItem] = {}
        self.operator: Dict[str, CommonItem] = {}
        self.kpi_stat = KpiStat()
        self.recommendation_engine = RecommendationEngine(calls_count_for_analyze=30)

        self.recommended_efficiency: Recommendation = Recommendation(None, "")
        self.recommended_approve: Recommendation = Recommendation(None, "")
        self.recommended_buyout: Recommendation = Recommendation(None, "")
        self.recommended_confirmation_price: Recommendation = Recommendation(None, "")

        self.approve_percent_fact: Optional[float] = None
        self.buyout_percent_fact: Optional[float] = None
        self.trash_percent: Optional[float] = None
        self.raw_to_approve_percent: Optional[float] = None
        self.raw_to_buyout_percent: Optional[float] = None
        self.non_trash_to_buyout_percent: Optional[float] = None
        self.max_confirmation_price: float = 0

        self.expecting_approve_leads: Optional[float] = None
        self.expecting_buyout_leads: Optional[float] = None

        self.operator_sorted: List[CommonItem] = []
        self.operator_recommended: Recommendation = Recommendation(None, "")
        self.approve_rate_plan: float = 0.0
        self.buyout_rate_plan: float = 0.0

        self.lead_container = SimpleNamespace(
            leads_non_trash_count=0,
            leads_approved_count=0,
            leads_buyout_count=0,
            leads_trash_count=0,
            leads_total_count=0,
            leads_raw_count=0
        )

        self.kpi_eff_need_correction = False
        self.kpi_eff_need_correction_str = ""
        self.kpi_app_need_correction = False
        self.kpi_app_need_correction_str = ""
        self.kpi_buyout_need_correction = False
        self.kpi_buyout_need_correction_str = ""

    def push_offer(self, offer_data: Dict, sql_data: Dict):
        offer_id = offer_data.get('id')
        if not offer_id or not str(offer_id).isdigit():
            return
        key = str(offer_id)
        if key not in self.offer:
            self.offer[key] = OfferItem(key, offer_data.get('name', ''))

    def push_lead(self, lead_data: Dict, sql_data: Dict):
        offer_id = lead_data.get('offer_id')
        aff_id = lead_data.get('aff_id')
        operator_name = lead_data.get('lv_operator', 'No operator')

        if str(offer_id).isdigit():
            key = str(offer_id)
            if key not in self.offer:
                self.offer[key] = OfferItem(key, lead_data.get('offer_name', ''))
            self.offer[key].push_lead(sql_data, offer_id=int(offer_id))

            self.offer[key].lead_container.leads_raw_count += 1
            self.offer[key].lead_container.leads_total_count += 1

            if not sql_data.get('lead_container_is_trash', False):
                self.offer[key].lead_container.leads_non_trash_count += 1
                if sql_data.get('lead_container_approved_at'):
                    self.offer[key].lead_container.leads_approved_count += 1
                    if sql_data.get('lead_container_buyout_at'):
                        self.offer[key].lead_container.leads_buyout_count += 1
            else:
                self.offer[key].lead_container.leads_trash_count += 1

        if str(aff_id).isdigit():
            key = str(aff_id)
            if key not in self.aff:
                self.aff[key] = CommonItem(key, f"Web #{key}")
            self.aff[key].push_lead(sql_data, offer_id=int(offer_id))

            self.aff[key].lead_container.leads_raw_count += 1
            self.aff[key].lead_container.leads_total_count += 1

            if not sql_data.get('lead_container_is_trash', False):
                self.aff[key].lead_container.leads_non_trash_count += 1
                if sql_data.get('lead_container_approved_at'):
                    self.aff[key].lead_container.leads_approved_count += 1
                    if sql_data.get('lead_container_buyout_at'):
                        self.aff[key].lead_container.leads_buyout_count += 1
            else:
                self.aff[key].lead_container.leads_trash_count += 1

        if operator_name:
            if operator_name not in self.operator:
                self.operator[operator_name] = CommonItem(operator_name, operator_name)
            self.operator[operator_name].push_lead(sql_data, offer_id=int(offer_id))

            self.operator[operator_name].lead_container.leads_raw_count += 1
            self.operator[operator_name].lead_container.leads_total_count += 1

            if not sql_data.get('lead_container_is_trash', False):
                self.operator[operator_name].lead_container.leads_non_trash_count += 1
                if sql_data.get('lead_container_approved_at'):
                    self.operator[operator_name].lead_container.leads_approved_count += 1
                    if sql_data.get('lead_container_buyout_at'):
                        self.operator[operator_name].lead_container.leads_buyout_count += 1
            else:
                self.operator[operator_name].lead_container.leads_trash_count += 1

        push_lead_to_engine(sql_data, int(offer_id) if str(offer_id).isdigit() else None, self.kpi_stat.stat)

    def push_call(self, call_data: Dict, sql_data: Dict):
        offer_id = call_data.get('offer_id')
        aff_id = call_data.get('aff_id')
        operator_name = call_data.get('lv_operator', 'No operator')

        if offer_id and str(offer_id).isdigit():
            key = str(offer_id)
            if key not in self.offer:
                offer_name = call_data.get('offer_name') or sql_data.get('offer_name', f'Offer #{key}')
                self.offer[key] = OfferItem(key, offer_name)
            self.offer[key].push_call(sql_data)

        if aff_id and str(aff_id).isdigit():
            key = str(aff_id)
            if key not in self.aff:
                self.aff[key] = CommonItem(key, f"Web #{key}")
            self.aff[key].push_call(sql_data)

        if operator_name and operator_name != 'un_operator':
            if operator_name not in self.operator:
                self.operator[operator_name] = CommonItem(operator_name, operator_name)
            self.operator[operator_name].push_call(sql_data)

        push_call_to_engine(sql_data, self.kpi_stat.stat)

    def _finalize_operators_and_affiliates(self, kpi_list: KpiList):
        for operator in self.operator.values():
            operator.recommended_efficiency = self.recommended_efficiency
            operator.recommended_approve = self.recommended_approve
            operator.recommended_buyout = self.recommended_buyout
            operator.recommended_confirmation_price = self.recommended_confirmation_price
            operator.finalize(kpi_list)

        for aff in self.aff.values():
            aff.recommended_efficiency = self.recommended_efficiency
            aff.recommended_approve = self.recommended_approve
            aff.recommended_buyout = self.recommended_buyout
            aff.recommended_confirmation_price = self.recommended_confirmation_price
            aff.finalize(kpi_list)

    def _calculate_category_metrics(self):
        total_non_trash = 0
        total_approved = 0
        total_buyout = 0
        total_trash = 0
        total_raw = 0
        total_leads = 0

        for offer in self.offer.values():
            total_non_trash += offer.lead_container.leads_non_trash_count
            total_approved += offer.lead_container.leads_approved_count
            total_buyout += offer.lead_container.leads_buyout_count
            total_trash += offer.lead_container.leads_trash_count
            total_raw += offer.lead_container.leads_raw_count
            total_leads += offer.lead_container.leads_total_count

        self.lead_container.leads_non_trash_count = total_non_trash
        self.lead_container.leads_approved_count = total_approved
        self.lead_container.leads_buyout_count = total_buyout
        self.lead_container.leads_trash_count = total_trash
        self.lead_container.leads_raw_count = total_raw
        self.lead_container.leads_total_count = total_leads

        self.approve_percent_fact = safe_div(total_approved, total_non_trash) * 100 if total_non_trash > 0 else 0
        self.buyout_percent_fact = safe_div(total_buyout, total_approved) * 100 if total_approved > 0 else 0
        self.trash_percent = safe_div(total_trash, total_leads) * 100 if total_leads > 0 else 0
        self.raw_to_approve_percent = safe_div(total_approved, total_raw) * 100 if total_raw > 0 else 0
        self.raw_to_buyout_percent = safe_div(total_buyout, total_raw) * 100 if total_raw > 0 else 0
        self.non_trash_to_buyout_percent = safe_div(total_buyout, total_non_trash) * 100 if total_non_trash > 0 else 0

    def _calculate_category_correction_flags(self):
        if self.recommended_efficiency and self.recommended_efficiency.value:
            current_eff = self.kpi_stat.effective_percent or 0
            rec_eff = safe_float(self.recommended_efficiency.value) or 0
            if abs(current_eff - rec_eff) > 5:
                self.kpi_eff_need_correction = True
                self.kpi_eff_need_correction_str = f"Эффективность категории: факт {current_eff:.1f}% vs рек. {rec_eff:.1f}%"

        if self.lead_container.leads_non_trash_count > 10:
            current_approve = self.approve_percent_fact or 0
            if current_approve < 30:
                self.kpi_app_need_correction = True
                self.kpi_app_need_correction_str = f"Низкий аппрув категории: {current_approve:.1f}%"

        if self.lead_container.leads_approved_count > 5:
            current_buyout = self.buyout_percent_fact or 0
            if current_buyout < 20:
                self.kpi_buyout_need_correction = True
                self.kpi_buyout_need_correction_str = f"Низкий выкуп категории: {current_buyout:.1f}%"

    def _calculate_recommended_efficiency(self):
        calls_total = 0
        leads_total = 0
        comment = ""

        if self.operator_recommended.value is None:
            return Recommendation(None, "Недостаточно операторов для расчета плана")

        if isinstance(self.operator_recommended.value, list) and not self.operator_recommended.value:
            for operator in self.operator_sorted:
                if (operator.kpi_stat.effective_rate > 0.0 and
                        operator.kpi_stat.calls_group_effective_count >= self.recommendation_engine.calls_count_for_analyze):
                    calls_total += operator.kpi_stat.calls_group_effective_count
                    leads_total += operator.kpi_stat.leads_effective_count
                    comment += f"{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"
        else:
            recommended_operators = self.operator_recommended.value
            if not isinstance(recommended_operators, list):
                recommended_operators = [recommended_operators] if recommended_operators else []

            for operator in self.operator_sorted:
                if operator.key in recommended_operators:
                    calls_total += operator.kpi_stat.calls_group_effective_count
                    leads_total += operator.kpi_stat.leads_effective_count
                    comment += f"{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"

        result = safe_div(calls_total, leads_total)
        comment += f"Звонков: {calls_total} лидов: {leads_total}\n"
        comment += f"Результат: {result}\n"

        if calls_total < self.recommendation_engine.calls_count_for_analyze:
            return Recommendation(None, comment + "Недостаточно звонков для принятия решения")
        else:
            return Recommendation(result, comment)

    def _calculate_recommended_approve(self):
        fact_approve = self.approve_percent_fact or 0

        if (self.expecting_approve_leads is not None and
                self.expecting_approve_leads > 0 and
                self.lead_container.leads_non_trash_count > 0):

            effective_percent = safe_float(self.kpi_stat.effective_percent) or 0

            if effective_percent > 0:
                perhaps_app_count = ((self.lead_container.leads_approved_count / (effective_percent / 100))
                                     - self.lead_container.leads_approved_count) * 0.3 + self.lead_container.leads_approved_count
            else:
                perhaps_app_count = self.lead_container.leads_approved_count

            rec_approve = safe_div(perhaps_app_count, self.lead_container.leads_non_trash_count) * 100
            rec_approve = max(0, min(rec_approve, 100))

            comment = f"Текущая эффективность: {effective_percent:.1f}%, коррекция -> вероятное к-во аппрувов: {perhaps_app_count:.0f}"

            if rec_approve < fact_approve:
                comment += f"\nФактический аппрув ({fact_approve:.1f}) выше рекоммендуемого ({rec_approve:.1f}), коррекция рекоммендации до фактического аппрува"
                rec_approve = fact_approve
            elif rec_approve > fact_approve + 5:
                comment += f"\nФактический аппрув ({fact_approve:.1f}) рекоммендуемый ({rec_approve:.1f}), выше на +5%, коррекция до верхней границы +5%"
                rec_approve = fact_approve + 5

            return Recommendation(rec_approve, comment)
        else:
            if fact_approve > 0:
                rec_approve = min(fact_approve * 1.05, 80)
                comment = f"Текущий аппрув: {fact_approve:.1f}%, рекомендуется: {rec_approve:.1f}%"
            else:
                rec_approve = 30.0
                comment = "Недостаточно данных для расчета, используется значение по умолчанию"

            return Recommendation(rec_approve, comment)

    def _calculate_recommended_buyout(self):
        current_buyout = self.buyout_percent_fact or 0

        if current_buyout > 0:
            recommended_buyout = current_buyout * 1.02
            recommended_buyout = max(0, min(recommended_buyout, 100))
            comment = f"Текущий выкуп: {current_buyout:.1f}%, поднимаем на 2%"
        else:
            recommended_buyout = 25.0
            comment = "Недостаточно данных для расчета, используется значение по умолчанию"

        return Recommendation(recommended_buyout, comment)

    def finalize(self, kpi_list: KpiList):
        self.kpi_eff_need_correction = False
        self.kpi_eff_need_correction_str = ""
        self.kpi_app_need_correction = False
        self.kpi_app_need_correction_str = ""
        self.kpi_buyout_need_correction = False
        self.kpi_buyout_need_correction_str = ""

        for offer in self.offer.values():
            offer.kpi_current_plan = kpi_list.find_kpi(None, str(offer.key), datetime.now().strftime('%Y-%m-%d'))
            offer.finalize(kpi_list)

        finalize_engine_stat(self.kpi_stat.stat, kpi_list)

        self.kpi_stat.calls_group_effective_count = self.kpi_stat.stat.calls_group_effective_count
        self.kpi_stat.leads_effective_count = self.kpi_stat.stat.leads_effective_count
        self.kpi_stat.effective_percent = self.kpi_stat.stat.effective_percent
        self.kpi_stat.effective_rate = self.kpi_stat.stat.effective_rate
        self.kpi_stat.expecting_effective_rate = self.kpi_stat.stat.expecting_effective_rate

        self._calculate_category_metrics()

        self.operator_sorted = self.recommendation_engine.sort_operators_by_efficiency(self.operator)
        self.operator_recommended = self.recommendation_engine.get_operators_for_recommendations(self.operator_sorted)

        self.recommended_efficiency = self._calculate_recommended_efficiency()

        self.max_confirmation_price = 0
        for offer in self.offer.values():
            if offer.kpi_current_plan and offer.kpi_current_plan.confirmation_price:
                self.max_confirmation_price = max(self.max_confirmation_price,
                                                  safe_float(offer.kpi_current_plan.confirmation_price))

        self.expecting_approve_leads = 0.0
        self.expecting_buyout_leads = 0.0
        has_none = False

        for offer in self.offer.values():
            if offer.expecting_approve_leads is not None:
                self.expecting_approve_leads += safe_float(offer.expecting_approve_leads)
            else:
                has_none = True

            if offer.expecting_buyout_leads is not None:
                self.expecting_buyout_leads += safe_float(offer.expecting_buyout_leads)
            else:
                has_none = True

        if has_none:
            self.expecting_approve_leads = None
            self.expecting_buyout_leads = None

        total_non_trash = self.lead_container.leads_non_trash_count
        total_approved = self.lead_container.leads_approved_count

        if total_non_trash > 0:
            weighted_approve_sum = 0.0
            total_weight = 0

            for offer in self.offer.values():
                if (offer.kpi_current_plan and
                        offer.kpi_current_plan.planned_approve is not None and
                        offer.lead_container.leads_non_trash_count > 0):
                    plan_approve = safe_float(offer.kpi_current_plan.planned_approve) or 0
                    weight = offer.lead_container.leads_non_trash_count

                    weighted_approve_sum += plan_approve * weight
                    total_weight += weight

            if total_weight > 0:
                self.approve_rate_plan = weighted_approve_sum / total_weight
            else:
                self.approve_rate_plan = 0
        else:
            self.approve_rate_plan = 0

        if total_approved > 0:
            weighted_buyout_sum = 0.0
            total_weight = 0

            for offer in self.offer.values():
                if (offer.kpi_current_plan and
                        offer.kpi_current_plan.planned_buyout is not None and
                        offer.lead_container.leads_approved_count > 0):
                    plan_buyout = safe_float(offer.kpi_current_plan.planned_buyout) or 0
                    weight = offer.lead_container.leads_approved_count

                    weighted_buyout_sum += plan_buyout * weight
                    total_weight += weight

            if total_weight > 0:
                self.buyout_rate_plan = weighted_buyout_sum / total_weight
            else:
                self.buyout_rate_plan = 0
        else:
            self.buyout_rate_plan = 0

        self.recommended_approve = self._calculate_recommended_approve()
        self.recommended_buyout = self._calculate_recommended_buyout()

        self.recommended_confirmation_price = Recommendation(
            self.max_confirmation_price,
            "Максимальный чек в группе"
        )

        for offer in self.offer.values():
            offer.recommended_efficiency = self.recommended_efficiency
            offer.recommended_approve = self.recommended_approve
            offer.recommended_buyout = self.recommended_buyout
            offer.recommended_confirmation_price = self.recommended_confirmation_price
            offer.calculate_correction_flags()

        self._finalize_operators_and_affiliates(kpi_list)

        self._calculate_category_correction_flags()


class Stat:
    def __init__(self):
        self.category: Dict[str, CategoryItem] = {}
        self.kpi_list: Optional[KpiList] = None
        self.leads_container_data: List[Dict] = []

    def _load_kpi_data(self, kpi_plans_data: List[Dict]):
        self.kpi_list = KpiList()
        for plan in kpi_plans_data or []:
            try:
                self.kpi_list.push_kpi(plan)
            except Exception as e:
                logger.error(f"KPI load error: {e}")

    def finalize_with_data(self, kpi_plans_data: List[Dict], leads_container_data: List[Dict]):
        self.leads_container_data = leads_container_data
        self._load_kpi_data(kpi_plans_data)
        self._process_leads_container_data()

        for cat in self.category.values():
            cat.finalize(self.kpi_list)

    def _process_leads_container_data(self):
        if not self.leads_container_data:
            logger.warning("No leads container data provided")
            return

        category_leads = {}
        offer_leads = {}

        for lead in self.leads_container_data:
            category_name = lead.get('category_name', 'No category')
            offer_id = str(lead.get('offer_id', ''))

            if category_name not in category_leads:
                category_leads[category_name] = {'raw': 0, 'non_trash': 0, 'approved': 0, 'buyout': 0}
            if offer_id not in offer_leads:
                offer_leads[offer_id] = {'raw': 0, 'non_trash': 0, 'approved': 0, 'buyout': 0}

            category_leads[category_name]['raw'] += 1
            offer_leads[offer_id]['raw'] += 1

            is_trash = lead.get('lead_container_is_trash', False)
            approved_at = lead.get('lead_container_approved_at')

            if approved_at:
                fake_approve_reason = DBService.is_fake_approve({
                    'status_verbose': lead.get('lead_container_status_verbose', ''),
                    'status_group': lead.get('lead_container_status_group', ''),
                    'approved_at': approved_at,
                    'canceled_at': lead.get('lead_container_canceled_at', '')
                })
                if not fake_approve_reason:
                    is_trash = False

            if not is_trash:
                category_leads[category_name]['non_trash'] += 1
                offer_leads[offer_id]['non_trash'] += 1

                if approved_at and not fake_approve_reason:
                    category_leads[category_name]['approved'] += 1
                    offer_leads[offer_id]['approved'] += 1

                    if lead.get('lead_container_buyout_at'):
                        fake_buyout_reason = DBService.is_fake_buyout({
                            'status_group': lead.get('lead_container_status_group', ''),
                            'buyout_at': lead.get('lead_container_buyout_at', '')
                        })
                        if not fake_buyout_reason:
                            category_leads[category_name]['buyout'] += 1
                            offer_leads[offer_id]['buyout'] += 1

        for cat_name, cat_data in category_leads.items():
            if cat_name in self.category:
                self.category[cat_name].lead_container.leads_raw_count = cat_data['raw']
                self.category[cat_name].lead_container.leads_non_trash_count = cat_data['non_trash']
                self.category[cat_name].lead_container.leads_approved_count = cat_data['approved']
                self.category[cat_name].lead_container.leads_buyout_count = cat_data['buyout']

        for offer_id, offer_data in offer_leads.items():
            for category in self.category.values():
                if offer_id in category.offer:
                    category.offer[offer_id].lead_container.leads_raw_count = offer_data['raw']
                    category.offer[offer_id].lead_container.leads_non_trash_count = offer_data['non_trash']
                    category.offer[offer_id].lead_container.leads_approved_count = offer_data['approved']
                    category.offer[offer_id].lead_container.leads_buyout_count = offer_data['buyout']

    def push_offer(self, sql_data: Dict):
        cat_name = sql_data.get('category_name', 'No category')
        if cat_name not in self.category:
            self.category[cat_name] = CategoryItem(cat_name, cat_name)
        offer_data = {'id': sql_data.get('id'), 'name': sql_data.get('name', '')}
        self.category[cat_name].push_offer(offer_data, sql_data)

    def push_lead(self, sql_data: Dict):
        cat_name = sql_data.get('category_name', 'No category')
        if cat_name not in self.category:
            self.category[cat_name] = CategoryItem(cat_name, cat_name)
        lead_data = {
            'offer_id': sql_data.get('offer_id'),
            'offer_name': sql_data.get('offer_name', ''),
            'aff_id': sql_data.get('aff_id'),
            'lv_operator': sql_data.get('lv_username', 'No operator')
        }
        self.category[cat_name].push_lead(lead_data, sql_data)

    def push_call(self, sql_data: Dict):
        cat_name = sql_data.get('category_name', 'No category')
        if cat_name not in self.category:
            self.category[cat_name] = CategoryItem(cat_name, cat_name)
        call_data = {
            'offer_id': sql_data.get('call_eff_offer_id') or sql_data.get('offer_id'),
            'offer_name': sql_data.get('offer_name', ''),
            'aff_id': sql_data.get('call_eff_affiliate_id'),
            'lv_operator': sql_data.get('lv_username', 'un_operator')
        }
        self.category[cat_name].push_call(call_data, sql_data)

    def get_categories_list(self) -> List[CategoryItem]:
        return list(self.category.values())


class OpAnalyzeKPI:
    ROW_TITLE_CATEGORY = "Категория"
    ROW_TITLE_OFFER = "Оффер"
    ROW_TITLE_OPERATOR = "Оператор"
    ROW_TITLE_AFF = "Вебмастер"

    col_recommendation = 13
    col_approve_recommendation = 21
    col_buyout_recommendation = 28

    def __init__(self):
        self.stat = Stat()

    def run_analysis_with_data(self, kpi_plans_data, offers_data, leads_data, calls_data, leads_container_data,
                               filters):
        logger.info(">>> Starting KPI analysis with pre-loaded data...")

        for offer in offers_data:
            self.stat.push_offer(offer)
        for lead in leads_data:
            self.stat.push_lead(lead)
        for call in calls_data:
            self.stat.push_call(call)

        self.stat.finalize_with_data(kpi_plans_data, leads_container_data)
        return self.stat

    def run_analysis(self, filters: Dict) -> Stat:
        logger.warning("Using deprecated run_analysis method - consider switching to run_analysis_with_data")

        kpi_plans = DBService.get_kpi_plans_data()
        offers = DBService.get_offers(filters)
        leads = DBService.get_leads(filters)
        calls = DBService.get_calls(filters)
        leads_container = DBService.get_leads_container(filters)

        return self.run_analysis_with_data(kpi_plans, offers, leads, calls, leads_container, filters)