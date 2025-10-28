# kpi_analyzer/kpi_analyzer.py
import re
from math import ceil
from datetime import datetime
from django.db.models import Q
from typing import Dict, List, Optional
from django.utils import timezone
from .models import KpiPlan

OP_ANALYZE_KPI_V2_SHEET_NAME = 'Анализ KPI'
ROW_TITLE_CATEGORY = "Категория"
ROW_TITLE_OFFER = "Оффер"
ROW_TITLE_AFF = "Веб"
ROW_TITLE_OPERATOR = "Оператор"
CALLS_COUNT_FOR_ANALYZE = 30
BLANK_KEY = ""

def safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0

def print_float(value: Optional[float]) -> str:
    return f"{value:.2f}" if value is not None else BLANK_KEY

def print_percent(prefix: str, numerator: float, denominator: float, suffix: str) -> str:
    return f"{prefix}{safe_div(numerator, denominator) * 100:.2f}%{suffix}" if denominator > 0 else BLANK_KEY

class Timesheet:
    def __init__(self, minutes_per_period=5):
        self.calls = {}
        self.operators = {}
        self.operators_count = 0
        self.working_interval_count = 0
        self.minutes_per_period = minutes_per_period

    def push_call(self, operator, created_at, duration):
        pattern = r"(\d{4}-\d{2}-\d{2} \d{1,2}):(\d{2})"
        match = re.match(pattern, created_at)
        if not match:
            raise ValueError("Неверный формат времени")
        prefix = match.group(1)
        minutes = int(match.group(2))
        minutes_round = minutes // self.minutes_per_period
        key = f"[{operator}][{prefix}][{minutes_round}]"
        if operator not in self.operators:
            self.operators[operator] = 1
            self.operators_count += 1
        else:
            self.operators[operator] += 1
        working_interval = ceil((duration / 60) / self.minutes_per_period)
        if working_interval < 1:
            working_interval = 1
        if key not in self.calls:
            self.calls[key] = working_interval
            self.working_interval_count += working_interval
        else:
            if self.calls[key] < working_interval:
                self.working_interval_count -= self.calls[key]
                self.calls[key] = working_interval
                self.working_interval_count += working_interval

    def get_working_time_minutes(self):
        return self.working_interval_count * self.minutes_per_period

    def get_operators_count(self):
        return self.operators_count

class Recommendation:
    def __init__(self, value, comment: str):
        self.value = value
        self.comment = comment

class Offer:
    def __init__(self, id: int, name: str, category_name: str):
        self.id = id
        self.name = name
        self.category = category_name
        self.key_category = self.category
        self.key_offer = f"[{self.id}] {self.name}"

class Lead:
    def __init__(self, call_eff_crm_lead_id: int, offer_id: int, offer_name: str, aff_id: int, lv_username: str, category_name: str):
        self.id = call_eff_crm_lead_id
        self.offer_id = offer_id
        self.offer_name = offer_name
        self.aff_id = aff_id
        self.lv_operator = lv_username
        self.category = category_name
        self.key_category = self.category
        self.key_offer = f"[{self.offer_id}] {self.offer_name}"
        self.key_aff = self.aff_id
        self.key_operator = self.lv_operator

class Call:
    def __init__(self, call_eff_id: int, call_eff_offer_id: int, offer_name: str, call_eff_affiliate_id: int, lv_username: str, category_name: str):
        self.id = call_eff_id
        self.offer_id = call_eff_offer_id
        self.offer_name = offer_name
        self.aff_id = call_eff_affiliate_id
        self.lv_operator = lv_username
        self.category = category_name
        self.key_category = self.category
        self.key_offer = f"[{self.offer_id}] {self.offer_name}"
        self.key_aff = self.aff_id
        self.key_operator = self.lv_operator

class KpiStat:
    def __init__(self):
        self.calls_group_effective_count = 0
        self.leads_effective_count = 0
        self.effective_rate = 0
        self.effective_percent = 0
        self.expecting_effective_rate = 0

    def push_lead(self, lead):
        self.leads_effective_count += 1

    def push_call(self, call):
        self.calls_group_effective_count += 1

    def finalyze(self, kpi_plans):
        self.effective_rate = safe_div(self.leads_effective_count, self.calls_group_effective_count)
        self.effective_percent = self.effective_rate * 100

class LeadContainer:
    def __init__(self):
        self.leads_non_trash_count = 0
        self.leads_approved_count = 0
        self.leads_buyout_count = 0

    def push_lead(self, lead):
        self.leads_non_trash_count += 1
        self.leads_approved_count += 1
        self.leads_buyout_count += 1

    def finalyze(self):
        pass

class CommonItem:
    def __init__(self, key: str, description: str):
        self.key = key
        self.description = description
        self.kpi_operator_effeciency_fact = None
        self.kpi_eff_need_correction = False
        self.kpi_eff_need_correction_str = ""
        self.kpi_app_need_correction = False
        self.kpi_app_need_correction_str = ""
        self.kpi_buyout_need_correction = False
        self.kpi_buyout_need_correction_str = ""
        self.kpi_confirmation_price_need_correction = False
        self.kpi_confirmation_price_need_correction_str = ""
        self.expecting_approve_leads = None
        self.expecting_buyout_leads = None
        self.kpi_stat = KpiStat()
        self.lead_container = LeadContainer()
        self.kpi_current_plan = None
        self.recommended_effeciency = None

    def push_lead_container(self, lead):
        self.lead_container.push_lead(lead)

    def push_lead(self, lead):
        self.kpi_stat.push_lead(lead)

    def push_call(self, call):
        self.kpi_stat.push_call(call)

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

    def finalyze(self, kpi_plans):
        self.kpi_stat.finalyze(kpi_plans)
        self.lead_container.finalyze()
        self.kpi_operator_effeciency_fact = self.kpi_stat.effective_rate
        if self.kpi_current_plan:
            self.expecting_approve_leads = self.lead_container.leads_non_trash_count * self.kpi_current_plan.planned_approve
            self.expecting_buyout_leads = self.lead_container.leads_approved_count * self.kpi_current_plan.planned_buyout
        if not self.kpi_current_plan:
            self.set_kpi_eff_need_correction("KPI не найден")
        elif not self.recommended_effeciency or self.recommended_effeciency.value is None:
            self.set_kpi_eff_need_correction("Не могу определить рекомендацию")
        else:
            if abs(self.recommended_effeciency.value - self.kpi_current_plan.operator_efficiency) > 0.2:
                self.set_kpi_eff_need_correction(
                    f"Отличия в рек. эффективности и плановой более чем на 0.2, рек: {self.recommended_effeciency.value} план: {self.kpi_current_plan.operator_efficiency}"
                )
            elif not self.kpi_current_plan.operator_efficiency:
                self.set_kpi_eff_need_correction(f"KPI эффективности не установлен '{self.kpi_current_plan.operator_efficiency}'")

class ItemCategory:
    def __init__(self, key: str, name: str):
        self.key = key
        self.description = name
        self.offer: Dict[int, CommonItem] = {}
        self.aff: Dict[int, CommonItem] = {}
        self.operator: Dict[str, CommonItem] = {}
        self.kpi_stat = KpiStat()
        self.lead_container = LeadContainer()
        self.approve_percent_fact = None
        self.expecting_approve_leads = 0
        self.approve_rate_plan = None
        self.recommended_approve = Recommendation(None, "")
        self.expecting_buyout_leads = 0
        self.buyout_rate_plan = None
        self.buyout_percent_fact = None
        self.recommended_buyout = Recommendation(None, "")
        self.recommended_confirmation_price = Recommendation(None, "")
        self.operator_sorted = []
        self.operator_recommended = None
        self.recommended_effeciency = None
        self.max_confirmation_price = 0

    def push_offer(self, offer: Offer):
        self.offer[offer.id] = CommonItem(str(offer.id), offer.name)

    def push_lead_container(self, lead: Lead):
        if lead.offer_id not in self.offer:
            self.offer[lead.offer_id] = CommonItem(str(lead.offer_id), lead.offer_name)
        self.offer[lead.offer_id].push_lead_container(lead)
        self.lead_container.push_lead(lead)

    def push_lead(self, lead: Lead):
        if lead.offer_id not in self.offer:
            self.offer[lead.offer_id] = CommonItem(str(lead.offer_id), lead.offer_name)
        if lead.aff_id not in self.aff:
            self.aff[lead.aff_id] = CommonItem(str(lead.aff_id), "")
        if lead.lv_operator not in self.operator:
            self.operator[lead.lv_operator] = CommonItem(lead.lv_operator, "")
        self.offer[lead.offer_id].push_lead(lead)
        self.aff[lead.aff_id].push_lead(lead)
        self.operator[lead.lv_operator].push_lead(lead)
        self.kpi_stat.push_lead(lead)

    def push_call(self, call: Call):
        if call.offer_id not in self.offer:
            self.offer[call.offer_id] = CommonItem(str(call.offer_id), call.offer_name)
        if call.aff_id not in self.aff:
            self.aff[call.aff_id] = CommonItem(str(call.aff_id), "")
        if call.lv_operator not in self.operator:
            self.operator[call.lv_operator] = CommonItem(call.lv_operator, "")
        self.offer[call.offer_id].push_call(call)
        self.aff[call.aff_id].push_call(call)
        self.operator[call.lv_operator].push_call(call)
        self.kpi_stat.push_call(call)

    def finalyze(self, kpi_plans):
        self.kpi_stat.finalyze(kpi_plans)
        self.lead_container.finalyze()
        for operator in self.operator.values():
            operator.finalyze(kpi_plans)
        self.operator_sorted = OpAnalyzeKpiV2.sort_to_array_operators(self.operator)
        self.operator_recommended = OpAnalyzeKpiV2.get_operators_for_recommendations(self.operator_sorted)
        self.recommended_effeciency = OpAnalyzeKpiV2.get_recommended_effeciency(self.operator_sorted, self.operator_recommended.value)
        self.approve_percent_fact = safe_div(self.lead_container.leads_approved_count, self.lead_container.leads_non_trash_count) * 100
        self.buyout_percent_fact = safe_div(self.lead_container.leads_buyout_count, self.lead_container.leads_approved_count) * 100

        import re
        current_date = timezone.now().strftime("%Y-%m-%d")

        for offer in self.offer.values():
            match = re.search(r'\[(\d+)\]', offer.key)
            if match:
                offer_id = int(match.group(1))
            else:

                offer_id = None

            if offer_id is not None:
                offer.kpi_current_plan = kpi_plans.filter(
                    offer_id=offer_id,
                    update_date=current_date
                ).first()
            else:
                offer.kpi_current_plan = None

            offer.recommended_effeciency = self.recommended_effeciency
            offer.finalyze(kpi_plans)

            if offer.kpi_current_plan:
                self.max_confirmation_price = max(self.max_confirmation_price,
                                                  offer.kpi_current_plan.confirmation_price)

            if offer.expecting_approve_leads is not None:
                self.expecting_approve_leads = (self.expecting_approve_leads or 0) + offer.expecting_approve_leads
            else:
                self.expecting_approve_leads = None

            if offer.expecting_buyout_leads is not None:
                self.expecting_buyout_leads = (self.expecting_buyout_leads or 0) + offer.expecting_buyout_leads
            else:
                self.expecting_buyout_leads = None

        if self.expecting_approve_leads:
            self.approve_rate_plan = safe_div(self.expecting_approve_leads, self.lead_container.leads_non_trash_count)
            perhaps_app_count = ((self.lead_container.leads_approved_count / (self.kpi_stat.effective_percent / 100)) - self.lead_container.leads_approved_count) * 0.3 + self.lead_container.leads_approved_count
            self.recommended_approve = Recommendation(
                safe_div(perhaps_app_count, self.lead_container.leads_non_trash_count) * 100,
                f"Текущая эффективность: {self.kpi_stat.effective_percent}, коррекция -> вероятное к-во аппрувов: {perhaps_app_count}"
            )
            if self.recommended_approve.value < self.approve_percent_fact:
                self.recommended_approve.comment += (f"\nФактический аппрув ({self.approve_percent_fact}) выше рекоммендуемого ({self.recommended_approve.value}), коррекция рекоммендации до фактического аппрува")
                self.recommended_approve.value = self.approve_percent_fact
            elif self.recommended_approve.value > self.approve_percent_fact + 5:
                self.recommended_approve.comment += (f"\nФактический аппрув ({self.approve_percent_fact}) рекоммендуемый ({self.recommended_approve.value}), выше на +5%, коррекция до верхней границы +5%")
                self.recommended_approve.value = self.approve_percent_fact + 5

        if self.expecting_buyout_leads:
            self.buyout_rate_plan = safe_div(self.expecting_buyout_leads, self.lead_container.leads_approved_count)
            self.recommended_buyout.value = self.buyout_percent_fact * 1.02 if self.buyout_percent_fact is not None else None
            self.recommended_buyout.comment = f"Текущий выкуп: {self.buyout_percent_fact}, поднимаем на 2%" if self.buyout_percent_fact is not None else ""

        self.recommended_confirmation_price.value = self.max_confirmation_price
        self.recommended_confirmation_price.comment = "Максимальный чек в группе"

        for offer in self.offer.values():
            offer.recommended_approve = self.recommended_approve
            if not offer.kpi_current_plan:
                offer.set_kpi_app_need_correction("KPI не найден")
            elif offer.kpi_current_plan.planned_approve is None or offer.kpi_current_plan.planned_approve < 0.1:
                offer.set_kpi_app_need_correction(f"KPI аппрува не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_approve}")
            elif offer.recommended_approve.value is None:
                offer.set_kpi_app_need_correction("Рекоммендация несформирована")
            elif abs(offer.kpi_current_plan.planned_approve - offer.recommended_approve.value) > 1:
                offer.set_kpi_app_need_correction(f"Плановый % аппрува ({offer.kpi_current_plan.planned_approve}) отличается от рекоммендации ({offer.recommended_approve.value}) более чем на 1%")

            offer.recommended_buyout = self.recommended_buyout
            if not offer.kpi_current_plan:
                offer.set_kpi_buyout_need_correction("KPI не найден")
            elif offer.kpi_current_plan.planned_buyout is None or offer.kpi_current_plan.planned_buyout < 0.1:
                offer.set_kpi_buyout_need_correction(f"KPI выкупа не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_buyout}")
            elif offer.recommended_buyout.value is None:
                offer.set_kpi_buyout_need_correction("Рекоммендация несформирована")
            elif abs(offer.kpi_current_plan.planned_buyout - offer.recommended_buyout.value) > 1:
                offer.set_kpi_buyout_need_correction(f"Плановый % выкупа ({offer.kpi_current_plan.planned_buyout}) отличается от рекоммендации ({offer.recommended_buyout.value}) более чем на 1%")

            offer.recommended_confirmation_price = self.recommended_confirmation_price
            if not offer.kpi_current_plan:
                offer.set_confirmation_price_need_correction("KPI не установлен")
            elif offer.kpi_current_plan.confirmation_price is None or offer.kpi_current_plan.confirmation_price < 1:
                offer.set_confirmation_price_need_correction("Чек подтверждения не установлен или предельно мал")
            elif self.max_confirmation_price == 0 or self.max_confirmation_price < 1:
                offer.set_confirmation_price_need_correction("Не удалось определить максимальный чек в группе или он предельно мал")
            elif offer.kpi_current_plan.confirmation_price != self.max_confirmation_price:
                offer.set_confirmation_price_need_correction(f"Текущий чек подтверждения ({offer.kpi_current_plan.confirmation_price}) < Максимального в группе ({self.max_confirmation_price})")

        for aff in self.aff.values():
            aff.finalyze(kpi_plans)

class OpAnalyzeKpiV2:
    vars = None
    calls_count_for_analyze = CALLS_COUNT_FOR_ANALYZE
    ROW_TITLE_CATEGORY = ROW_TITLE_CATEGORY
    ROW_TITLE_OFFER = ROW_TITLE_OFFER
    ROW_TITLE_AFF = ROW_TITLE_AFF
    ROW_TITLE_OPERATOR = ROW_TITLE_OPERATOR

    @staticmethod
    def vars_proceed():
        return {
            "sheetName": OP_ANALYZE_KPI_V2_SHEET_NAME,
            "date_from": None,
            "date_to": None,
            "group_rows": "Да",
            "advertiser": "",
            "output": "",
            "aff_id": None,
            "category": "",
            "offer_id": None,
            "lv_op": "",
            "col_recommendation": 18,
            "col_approve_recommendation": 25,
            "col_buyout_recommendation": 32,
            "range_full": "C:AV",
            "range_start_row": 13,
            "range_start": "C1",
        }

    @classmethod
    def get_vars(cls):
        if cls.vars is None:
            cls.vars = cls.vars_proceed()
        return cls.vars

    @staticmethod
    def sort_to_array_operators(operators: Dict[str, CommonItem]) -> List[CommonItem]:
        r1 = [op for op in operators.values() if op.kpi_stat.calls_group_effective_count >= CALLS_COUNT_FOR_ANALYZE and op.kpi_stat.effective_rate > 0.0]
        r2 = [op for op in operators.values() if not (op.kpi_stat.calls_group_effective_count >= CALLS_COUNT_FOR_ANALYZE and op.kpi_stat.effective_rate > 0.0)]
        r1.sort(key=lambda x: x.kpi_stat.effective_rate)
        return r1 + r2

    @staticmethod
    def get_operators_for_recommendations(operators: List[CommonItem]) -> Recommendation:
        eff_operators = sum(1 for op in operators if op.kpi_stat.effective_rate > 0.0 and op.kpi_stat.calls_group_effective_count >= CALLS_COUNT_FOR_ANALYZE)
        str_comment = f"Операторов для анализа всего: {eff_operators}\n"
        eff_operators = round(eff_operators * 0.4)
        if eff_operators < 3:
            return Recommendation(None, str_comment + f"Недостаточно операторов для расчета плана ({eff_operators})")
        if eff_operators > 5:
            eff_operators = 5
        r = []
        str_comment += f"Операторов для расчета эффективности: {eff_operators}\n--\n"
        calls = 0
        leads = 0
        for i, op in enumerate(operators):
            if len(r) >= eff_operators:
                break
            if op.kpi_stat.effective_rate > 0.0 and op.kpi_stat.calls_group_effective_count >= CALLS_COUNT_FOR_ANALYZE:
                r.append(op.key)
                str_comment += f"\t{op.key} звонков: {op.kpi_stat.calls_group_effective_count} аппрувов: {op.kpi_stat.leads_effective_count}\n"
                calls += op.kpi_stat.calls_group_effective_count
                leads += op.kpi_stat.leads_effective_count
        str_comment += "--\n"
        str_comment += f"Звонков: {calls} лидов: {leads}\n"
        str_comment += f"Результат: {safe_div(calls, leads)}\n"
        return Recommendation(r, str_comment)

    @staticmethod
    def get_recommended_effeciency(operators: List[CommonItem], top_operators: List[str]) -> Recommendation:
        if not top_operators:
            return Recommendation(None, "Недостаточно операторов для принятия решения")
        calls = 0
        leads = 0
        str_comment = ""
        for op in operators:
            if op.key not in top_operators:
                continue
            str_comment += f"\t{op.key} звонков: {op.kpi_stat.calls_group_effective_count} аппрувов: {op.kpi_stat.leads_effective_count}\n"
            calls += op.kpi_stat.calls_group_effective_count
            leads += op.kpi_stat.leads_effective_count
        result = safe_div(calls, leads)
        str_comment += "--\n"
        str_comment += f"Звонков: {calls} лидов: {leads}\n"
        str_comment += f"Результат: {result}\n"
        if calls < CALLS_COUNT_FOR_ANALYZE:
            return Recommendation(None, str_comment + "Недостаточно звонков для принятия решения")
        return Recommendation(result, str_comment)

    @staticmethod
    def print_pd_category(pd: List[List[str]], category: ItemCategory):
        i = len(pd)
        pd.append([])
        pd[i].append(ROW_TITLE_CATEGORY)
        pd[i].append(category.key)
        pd[i].extend([BLANK_KEY] * 4)
        pd[i].append(category.kpi_stat.calls_group_effective_count)
        pd[i].append(category.kpi_stat.leads_effective_count)
        pd[i].append(print_float(category.kpi_stat.effective_percent))
        pd[i].append(BLANK_KEY)
        pd[i].append(print_float(category.kpi_stat.effective_rate))
        pd[i].append(print_float(category.kpi_stat.expecting_effective_rate))
        pd[i].extend([BLANK_KEY] * 2)
        pd[i].append(print_float(category.recommended_effeciency.value) if category.recommended_effeciency else BLANK_KEY)
        pd[i].extend([BLANK_KEY] * 3)
        pd[i].append(category.lead_container.leads_non_trash_count)
        pd[i].append(category.lead_container.leads_approved_count)
        pd[i].append(print_percent("", category.lead_container.leads_approved_count, category.lead_container.leads_non_trash_count, ""))
        pd[i].append(print_float(category.approve_rate_plan) + "%" if category.approve_rate_plan is not None else BLANK_KEY)
        pd[i].append(print_float(category.recommended_approve.value) if category.recommended_approve else BLANK_KEY)
        pd[i].extend([BLANK_KEY] * 3)
        pd[i].append(category.lead_container.leads_buyout_count)
        pd[i].append(category.buyout_percent_fact if category.buyout_percent_fact is not None else BLANK_KEY)
        pd[i].append(category.buyout_rate_plan if category.buyout_rate_plan is not None else BLANK_KEY)
        pd[i].append(category.recommended_buyout.value if category.recommended_buyout else BLANK_KEY)
        pd[i].extend([BLANK_KEY] * 8)
        pd[i].append(category.max_confirmation_price)
        pd[i].extend([BLANK_KEY] * 5)

    @staticmethod
    def print_pd_offer(pd: List[List[str]], offer: CommonItem, category: ItemCategory):
        i = len(pd)
        pd.append([])
        pd[i].append(ROW_TITLE_OFFER)
        pd[i].append(category.key)
        pd[i].append(offer.key)
        pd[i].append(offer.description)
        pd[i].extend([BLANK_KEY] * 2)
        pd[i].append(offer.kpi_stat.calls_group_effective_count)
        pd[i].append(offer.kpi_stat.leads_effective_count)
        pd[i].append(print_float(offer.kpi_stat.effective_percent))
        pd[i].append(BLANK_KEY)
        pd[i].append(print_float(offer.kpi_stat.effective_rate))
        if offer.kpi_current_plan:
            pd[i].append(print_float(offer.kpi_current_plan.operator_efficiency))
            pd[i].append(str(offer.kpi_current_plan.update_date))
        else:
            pd[i].extend([BLANK_KEY] * 2)
        pd[i].extend([BLANK_KEY] * 1)
        pd[i].append(print_float(offer.recommended_effeciency.value) if offer.recommended_effeciency else BLANK_KEY)
        pd[i].append(offer.kpi_current_plan.operator_effeciency_update_date if offer.kpi_current_plan else BLANK_KEY)
        pd[i].append(offer.kpi_eff_need_correction)
        pd[i].append(BLANK_KEY)
        pd[i].append(offer.lead_container.leads_non_trash_count)
        pd[i].append(offer.lead_container.leads_approved_count)
        pd[i].append(print_percent("", offer.lead_container.leads_approved_count, offer.lead_container.leads_non_trash_count, ""))
        pd[i].append(print_float(offer.kpi_current_plan.planned_approve) if offer.kpi_current_plan else BLANK_KEY)
        pd[i].append(print_float(offer.recommended_approve.value) if offer.recommended_approve else BLANK_KEY)
        pd[i].append(offer.kpi_current_plan.planned_approve_update_date if offer.kpi_current_plan else BLANK_KEY)
        pd[i].append(offer.kpi_app_need_correction)
        pd[i].extend([BLANK_KEY] * 3)
        pd[i].append(print_float(offer.kpi_current_plan.planned_buyout) if offer.kpi_current_plan else BLANK_KEY)
        pd[i].append(print_float(offer.recommended_buyout.value) if offer.recommended_buyout else BLANK_KEY)
        pd[i].append(offer.kpi_current_plan.planned_buyout_update_date if offer.kpi_current_plan else BLANK_KEY)
        pd[i].append(offer.kpi_buyout_need_correction)
        pd[i].append("[ >>>> ]")
        pd[i].append(print_float(offer.recommended_effeciency.value) if offer.recommended_effeciency else BLANK_KEY)
        pd[i].append(offer.kpi_eff_need_correction)
        pd[i].append(print_float(offer.recommended_approve.value) if offer.recommended_approve else BLANK_KEY)
        pd[i].append(offer.kpi_app_need_correction)
        pd[i].append(print_float(offer.recommended_confirmation_price.value) if offer.recommended_confirmation_price else BLANK_KEY)
        pd[i].append(offer.kpi_confirmation_price_need_correction)
        pd[i].append(print_float(offer.recommended_buyout.value) if offer.recommended_buyout else BLANK_KEY)
        pd[i].append(offer.kpi_buyout_need_correction)
        pd[i].append(f"https://admin.crm.itvx.biz/partners/tloffer/{offer.key}/change/")

    @staticmethod
    def print_pd_aff(pd: List[List[str]], aff: CommonItem):
        i = len(pd)
        pd.append([])
        pd[i].append(ROW_TITLE_AFF)
        pd[i].extend([BLANK_KEY] * 3)
        pd[i].append(aff.key)
        pd[i].append(BLANK_KEY)
        pd[i].append(aff.kpi_stat.calls_group_effective_count)
        pd[i].append(aff.kpi_stat.leads_effective_count)
        pd[i].append(print_float(aff.kpi_stat.effective_percent))
        pd[i].append(BLANK_KEY)
        pd[i].append(print_float(aff.kpi_stat.effective_rate))
        pd[i].extend([BLANK_KEY] * 31)

    @staticmethod
    def print_pd_operator(pd: List[List[str]], operator: CommonItem):
        i = len(pd)
        pd.append([])
        pd[i].append(ROW_TITLE_OPERATOR)
        pd[i].extend([BLANK_KEY] * 4)
        pd[i].append(operator.key)
        pd[i].append(operator.kpi_stat.calls_group_effective_count)
        pd[i].append(operator.kpi_stat.leads_effective_count)
        pd[i].append(print_float(operator.kpi_stat.effective_percent))
        pd[i].append(BLANK_KEY)
        pd[i].append(print_float(operator.kpi_stat.effective_rate))
        pd[i].extend([BLANK_KEY] * 31)

    class Stat:
        def __init__(self):
            self.category: Dict[str, ItemCategory] = {}
            self.kpi_plans = KpiPlan.objects.all()

        def push_offer(self, offer):
            if offer.category_name not in self.category:
                self.category[offer.category_name] = ItemCategory(offer.category_name, offer.category_name)
            self.category[offer.category_name].push_offer(Offer(offer.id, offer.name, offer.category_name))

        def push_lead_container(self, lead):
            if lead.category_name not in self.category:
                self.category[lead.category_name] = ItemCategory(lead.category_name, lead.category_name)
            self.category[lead.category_name].push_lead_container(Lead(
                lead.call_eff_crm_lead_id, lead.offer_id, lead.offer.name, lead.aff_id, lead.lv_username, lead.category_name
            ))

        def push_lead(self, lead):
            if lead.category_name not in self.category:
                self.category[lead.category_name] = ItemCategory(lead.category_name, lead.category_name)
            self.category[lead.category_name].push_lead(Lead(
                lead.call_eff_crm_lead_id, lead.offer_id, lead.offer.name, lead.aff_id, lead.lv_username, lead.category_name
            ))

        def push_call(self, call):
            if call.category_name not in self.category:
                self.category[call.category_name] = ItemCategory(call.category_name, call.category_name)
            self.category[call.category_name].push_call(Call(
                call.call_eff_id, call.offer_id, call.offer.name, call.call_eff_affiliate_id, call.lv_username, call.category_name
            ))

        def finalyze(self):
            for category in self.category.values():
                category.finalyze(self.kpi_plans)