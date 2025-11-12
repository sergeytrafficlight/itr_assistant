from typing import Dict, List, Any, Optional
from datetime import datetime, date
from decimal import Decimal
import logging
from .statistics import safe_div, CallEfficiencyStat, LeadContainerStat, AggregatedCallEfficiencyStat
from .recommendation_engine import RecommendationEngine, Recommendation

logger = logging.getLogger(__name__)


class OpAnalyzeKPI:
    calls_count_for_analyze = 30
    ROW_TITLE_CATEGORY = "Категория"
    ROW_TITLE_OFFER = "Оффер"
    ROW_TITLE_AFF = "Веб"
    ROW_TITLE_OPERATOR = "Оператор"

    def __init__(self):
        self.vars = None
        self.recommendation_engine = RecommendationEngine()

    def vars_proceed(self):
        return {
            'sheetName': 'Анализ KPI',
            'date_from': '',
            'date_to': '',
            'group_rows': 'Нет',
            'advertiser': '',
            'output': 'Все',
            'aff_id': '',
            'category': '',
            'offer_id': '',
            'lv_op': '',
            'col_recommendation': 18,
            'col_approve_recommendation': 25,
            'col_buyout_recommendation': 32,
            'range_full': 'C:AV',
            'range_start_row': 13,
            'range_start': 'C1',
        }

    def get_vars(self):
        if self.vars is None:
            self.vars = self.vars_proceed()
        return self.vars


class CommonItem:
    def __init__(self, key: str, description: str):
        self.key = key
        self.description = description
        self.kpi_operator_efficiency_fact = None
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
        self.kpi_stat = AggregatedCallEfficiencyStat()
        self.kpi_current_plan = None
        self.recommended_effeciency = Recommendation(None, "")
        self.recommended_approve = None
        self.recommended_buyout = None
        self.recommended_confirmation_price = None
        self.leads_non_trash_count = 0
        self.leads_approved_count = 0
        self.leads_buyout_count = 0

    def push_lead(self, sql_data: Dict):
        self.kpi_stat.push_lead(sql_data)

    def push_call(self, sql_data: Dict):
        self.kpi_stat.push_call(sql_data)

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

    def finalyze(self, kpi_list):
        self.kpi_stat.finalyze(kpi_list)
        self.kpi_operator_efficiency_fact = self.kpi_stat.effective_rate

        if self.kpi_current_plan is not None:
            self.expecting_approve_leads = self.leads_non_trash_count * self.kpi_current_plan.planned_approve
            self.expecting_buyout_leads = self.leads_approved_count * self.kpi_current_plan.planned_buyout

        if self.kpi_current_plan is None:
            self.set_kpi_eff_need_correction("KPI не найден")
        elif self.recommended_effeciency.value is None:
            self.set_kpi_eff_need_correction("Не могу определить рекоммендацию")
        else:
            if abs(self.recommended_effeciency.value - self.kpi_current_plan.operator_efficiency) > 0.2:
                self.set_kpi_eff_need_correction(
                    f"Отличия в рек. эффективности и плановой более чем на 0.2, рек:{self.recommended_effeciency.value} план: {self.kpi_current_plan.operator_efficiency}"
                )
            elif self.kpi_current_plan.operator_efficiency is None or self.kpi_current_plan.operator_efficiency == "" or self.kpi_current_plan.operator_efficiency == 0:
                self.set_kpi_eff_need_correction(
                    f"KPI эффективности не установлен '{self.kpi_current_plan.operator_efficiency}'")


class CategoryItem:
    def __init__(self, key: str, name: str):
        self.key = key
        self.description = name
        self.offer: Dict[str, CommonItem] = {}
        self.aff: Dict[str, CommonItem] = {}
        self.operator: Dict[str, CommonItem] = {}
        self.kpi_stat = AggregatedCallEfficiencyStat()
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
        self.leads_non_trash_count = 0
        self.leads_approved_count = 0
        self.leads_buyout_count = 0
        self.recommendation_engine = RecommendationEngine()

    def push_lead(self, sql_data: Dict):
        offer_id = sql_data.get('offer_id', 0)
        offer_name = sql_data.get('offer_name', 'Без оффера')
        aff_id = sql_data.get('aff_id', 0)
        operator_name = sql_data.get('operator_name', 'Без оператора')

        if offer_id not in self.offer:
            self.offer[offer_id] = CommonItem(str(offer_id), offer_name)

        if aff_id not in self.aff:
            self.aff[aff_id] = CommonItem(str(aff_id), "")

        if operator_name not in self.operator:
            self.operator[operator_name] = CommonItem(operator_name, "")

        self.offer[offer_id].push_lead(sql_data)
        self.aff[aff_id].push_lead(sql_data)
        self.operator[operator_name].push_lead(sql_data)
        self.kpi_stat.push_lead(sql_data)

    def push_call(self, sql_data: Dict):
        offer_id = sql_data.get('offer_id', 0)
        offer_name = sql_data.get('offer_name', 'Без оффера')
        aff_id = sql_data.get('aff_id', 0)
        operator_name = sql_data.get('operator_name', 'Без оператора')

        if offer_id not in self.offer:
            self.offer[offer_id] = CommonItem(str(offer_id), offer_name)

        if aff_id not in self.aff:
            self.aff[aff_id] = CommonItem(str(aff_id), "")

        if operator_name not in self.operator:
            self.operator[operator_name] = CommonItem(operator_name, "")

        self.offer[offer_id].push_call(sql_data)
        self.aff[aff_id].push_call(sql_data)
        self.operator[operator_name].push_call(sql_data)
        self.kpi_stat.push_call(sql_data)

    def finalyze(self, kpi_list):
        logger.debug(f"Финализация категории {self.key}")

        from datetime import datetime
        current_date = datetime.now().strftime('%Y-%m-%d')

        self.kpi_stat.finalyze(kpi_list)

        for operator in self.operator.values():
            operator.finalyze(kpi_list)

        self.operator_sorted = self.recommendation_engine.sort_operators_by_efficiency(self.operator)
        self.operator_recommended = self.recommendation_engine.get_operators_for_recommendations(self.operator_sorted)
        self.recommended_effeciency = self.recommendation_engine.get_recommended_efficiency(
            self.operator_sorted, self.operator_recommended.value
        )

        self.leads_non_trash_count = sum(offer.leads_non_trash_count for offer in self.offer.values())
        self.leads_approved_count = sum(offer.leads_approved_count for offer in self.offer.values())
        self.leads_buyout_count = sum(offer.leads_buyout_count for offer in self.offer.values())

        self.approve_percent_fact = safe_div(self.leads_approved_count, self.leads_non_trash_count) * 100
        self.buyout_percent_fact = safe_div(self.leads_buyout_count, self.leads_approved_count) * 100

        self.max_confirmation_price = 0
        for offer in self.offer.values():
            offer.kpi_current_plan = kpi_list.find_kpi(None, offer.key, current_date)
            offer.recommended_effeciency = self.recommended_effeciency
            offer.finalyze(kpi_list)

            if offer.kpi_current_plan is not None:
                self.max_confirmation_price = max(self.max_confirmation_price,
                                                  offer.kpi_current_plan.confirmation_price)

            if offer.expecting_approve_leads is not None:
                if self.expecting_approve_leads is not None:
                    self.expecting_approve_leads += offer.expecting_approve_leads
            else:
                self.expecting_approve_leads = None

            if offer.expecting_buyout_leads is not None:
                if self.expecting_buyout_leads is not None:
                    self.expecting_buyout_leads += offer.expecting_buyout_leads
            else:
                self.expecting_buyout_leads = None

        if self.expecting_approve_leads:
            self.approve_rate_plan = safe_div(self.expecting_approve_leads, self.leads_non_trash_count)

            effective_percent_value = self.kpi_stat.effective_percent or 0.0
            if effective_percent_value > 0:
                perhaps_app_count = ((self.leads_approved_count / (
                        effective_percent_value / 100)) - self.leads_approved_count) * 0.3 + self.leads_approved_count
            else:
                perhaps_app_count = self.leads_approved_count

            self.recommended_approve = Recommendation(
                safe_div(perhaps_app_count, self.leads_non_trash_count) * 100,
                f"Текущая эффективность: {effective_percent_value}, коррекция -> вероятное к-во аппрувов: {perhaps_app_count}"
            )

            if self.recommended_approve.value < self.approve_percent_fact:
                self.recommended_approve.comment += f"\nФактический аппрув ({self.approve_percent_fact}) выше рекоммендуемого ({self.recommended_approve.value}), коррекция рекоммендации до фактического аппрува"
                self.recommended_approve.value = self.approve_percent_fact
            elif self.recommended_approve.value > self.approve_percent_fact + 5:
                self.recommended_approve.comment += f"\nФактический аппрув ({self.approve_percent_fact}) рекоммендуемый ({self.recommended_approve.value}), выше на +5%, коррекция до верхней границы +5%"
                self.recommended_approve.value = self.approve_percent_fact + 5

        if self.expecting_buyout_leads:
            self.buyout_rate_plan = safe_div(self.expecting_buyout_leads, self.leads_approved_count)

        self.recommended_buyout = Recommendation(
            self.buyout_percent_fact * 1.02,
            f"Текущий выкуп: {self.buyout_percent_fact}, поднимаем на 2%"
        )

        self.recommended_confirmation_price = Recommendation(
            self.max_confirmation_price,
            "Максимальный чек в группе"
        )

        for offer in self.offer.values():
            offer.recommended_approve = self.recommended_approve

            if offer.kpi_current_plan is None:
                offer.set_kpi_app_need_correction("KPI не найден")
            elif offer.kpi_current_plan.planned_approve is None or offer.kpi_current_plan.planned_approve < 0.1:
                offer.set_kpi_app_need_correction(
                    f"KPI аппрува не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_approve}")
            elif offer.recommended_approve.value is None:
                offer.set_kpi_app_need_correction("Рекоммендация несформирована")
            elif abs(offer.kpi_current_plan.planned_approve - offer.recommended_approve.value) > 1:
                offer.set_kpi_app_need_correction(
                    f"Плановый % аппрува ({offer.kpi_current_plan.planned_approve}) отличается от рекоммендации ({offer.recommended_approve.value}) более чем на 1%")

            offer.recommended_buyout = self.recommended_buyout
            if offer.kpi_current_plan is None:
                offer.set_kpi_buyout_need_correction("KPI не найден")
            elif offer.kpi_current_plan.planned_buyout is None or offer.kpi_current_plan.planned_buyout < 0.1:
                offer.set_kpi_buyout_need_correction(
                    f"KPI выкупа не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_buyout}")
            elif offer.recommended_buyout.value is None:
                offer.set_kpi_buyout_need_correction("Рекоммендация несформирована")
            elif abs(offer.kpi_current_plan.planned_buyout - offer.recommended_buyout.value) > 1:
                offer.set_kpi_buyout_need_correction(
                    f"Плановый % выкупа ({offer.kpi_current_plan.planned_buyout}) отличается от рекоммендации ({offer.recommended_buyout.value}) более чем на 1%")

            offer.recommended_confirmation_price = self.recommended_confirmation_price
            if offer.kpi_current_plan is None:
                offer.set_confirmation_price_need_correction("KPI не установлен")
            elif offer.kpi_current_plan.confirmation_price is None or offer.kpi_current_plan.confirmation_price < 1:
                offer.set_confirmation_price_need_correction("Чек подтверждения не установлен или предельно мал")
            elif self.max_confirmation_price == 0 or self.max_confirmation_price < 1:
                offer.set_confirmation_price_need_correction(
                    "Не удалось определить максимальный чек в группе или он предельно мал")
            elif offer.kpi_current_plan.confirmation_price != self.max_confirmation_price:
                offer.set_confirmation_price_need_correction(
                    f"Текущий чек подтверждения ({offer.kpi_current_plan.confirmation_price}) < Максимального в группе ({self.max_confirmation_price})")

        for aff in self.aff.values():
            aff.finalyze(kpi_list)

        logger.debug(
            f"Категория {self.key} финализирована: calls={self.kpi_stat.calls_group_effective_count}, leads={self.kpi_stat.leads_effective_count}")


class GlobalDataAggregator:
    def __init__(self, global_lead_container):
        self.global_lead_container = global_lead_container
        self.category_stats = {}

    def aggregate_by_category_and_offer(self, calls_data, leads_data):
        category_offer_leads = {}
        for lead_id, lead in self.global_lead_container.leads.items():
            for lc_data in self.global_lead_container.raw_container_data:
                if lc_data.get('lead_container_crm_lead_id') == lead_id:
                    category_name = lc_data.get('category_name', 'Без категории')
                    offer_id = lc_data.get('offer_id', 0)
                    offer_name = lc_data.get('offer_name', 'Без оффера')
                    key = f"{category_name}_{offer_id}"
                    if key not in category_offer_leads:
                        category_offer_leads[key] = {
                            'category_name': category_name,
                            'offer_id': offer_id,
                            'offer_name': offer_name,
                            'leads_non_trash_count': 0,
                            'leads_approved_count': 0,
                            'leads_buyout_count': 0
                        }
                    if lead.is_trash == 0:
                        category_offer_leads[key]['leads_non_trash_count'] += 1
                    if lead.is_approve:
                        category_offer_leads[key]['leads_approved_count'] += 1
                    if lead.is_buyout:
                        category_offer_leads[key]['leads_buyout_count'] += 1
                    break
        for category_name in self.get_all_categories():
            if category_name not in self.category_stats:
                self.category_stats[category_name] = CategoryItem(category_name, category_name)
            category_stat = self.category_stats[category_name]
            category_calls = [c for c in calls_data if c.get('category_name') == category_name]
            category_leads = [l for l in leads_data if l.get('category_name') == category_name]
            for call in category_calls:
                category_stat.push_call(call)
            for lead in category_leads:
                category_stat.push_lead(lead)
            for key, offer_data in category_offer_leads.items():
                if offer_data['category_name'] == category_name:
                    offer_id = offer_data['offer_id']
                    if offer_id not in category_stat.offer:
                        category_stat.offer[offer_id] = CommonItem(str(offer_id), offer_data['offer_name'])
                    category_stat.offer[offer_id].leads_non_trash_count = offer_data['leads_non_trash_count']
                    category_stat.offer[offer_id].leads_approved_count = offer_data['leads_approved_count']
                    category_stat.offer[offer_id].leads_buyout_count = offer_data['leads_buyout_count']

    def get_all_categories(self):
        categories = set()
        for lc_data in self.global_lead_container.raw_container_data:
            categories.add(lc_data.get('category_name', 'Без категории'))
        for call in self.global_lead_container.calls:
            lead = self.global_lead_container.leads.get(call.crm_lead_id)
            if lead:
                for lc_data in self.global_lead_container.raw_container_data:
                    if lc_data.get('lead_container_crm_lead_id') == call.crm_lead_id:
                        categories.add(lc_data.get('category_name', 'Без категории'))
                        break
        return categories

    def get_category_stats(self):
        return self.category_stats


class KpiPlan:
    def __init__(self, plan_data: Dict):
        self.id = plan_data.get('call_eff_kpi_id')
        self.period_date = plan_data.get('call_eff_period_date')
        self.offer_id = plan_data.get('call_eff_offer_id')
        self.affiliate_id = plan_data.get('call_eff_affiliate_id')

        def convert_value(value):
            if isinstance(value, Decimal):
                return float(value)
            return value

        self.operator_efficiency = convert_value(plan_data.get('call_eff_operator_efficiency'))
        self.planned_approve = convert_value(plan_data.get('call_eff_planned_approve'))
        self.planned_buyout = convert_value(plan_data.get('call_eff_planned_buyout'))
        self.confirmation_price = convert_value(plan_data.get('call_eff_confirmation_price'))

        self.update_date = plan_data.get('call_eff_plan_update_date')
        self.operator_effeciency_update_date = plan_data.get('call_eff_operator_efficiency_update_date')
        self.planned_approve_update_date = plan_data.get('call_eff_approve_update_date')
        self.planned_buyout_update_date = plan_data.get('call_eff_buyout_update_date')


class OptimizedKPIList:
    def __init__(self, kpi_plans_data: List[Dict]):
        self.plans = [KpiPlan(plan_data) for plan_data in kpi_plans_data]
        self._build_search_index()

    def _build_search_index(self):
        self._date_index = {}
        self._offer_index = {}
        for plan in self.plans:
            date_key = str(plan.period_date)
            self._date_index.setdefault(date_key, []).append(plan)
            if plan.offer_id:
                offer_key = str(plan.offer_id)
                self._offer_index.setdefault(offer_key, []).append(plan)

    def find_kpi(self, affiliate_id: Optional[int], offer_id: int, date_str: str) -> Optional[KpiPlan]:
        if not date_str:
            return None

        date_str = str(date_str).split()[0]
        target_date = self._parse_date(date_str)
        if not target_date:
            return None

        date_key = str(target_date)
        date_candidates = self._date_index.get(date_key, [])

        if affiliate_id is not None:
            for plan in date_candidates:
                if (str(plan.offer_id) == str(offer_id) and
                        str(plan.affiliate_id) == str(affiliate_id)):
                    return plan

        if offer_id and str(offer_id).isdigit():
            for plan in date_candidates:
                if str(plan.offer_id) == str(offer_id):
                    return plan

        if offer_id and str(offer_id).isdigit():
            offer_candidates = self._offer_index.get(str(offer_id), [])
            if offer_candidates:
                nearest_plan = min(
                    offer_candidates,
                    key=lambda p: abs((self._parse_date(p.period_date) - target_date).days)
                    if self._parse_date(p.period_date) else float('inf')
                )
                return nearest_plan

        if date_candidates:
            return date_candidates[0]

        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        if not date_str:
            return None
        try:
            if isinstance(date_str, date):
                return date_str
            if isinstance(date_str, datetime):
                return date_str.date()
            return datetime.strptime(str(date_str).split()[0], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None


class Grouper:
    def __init__(self):
        self.groups = []

    def push_group(self, start_row: int, end_row: int):
        self.groups.append({'start': start_row, 'end': end_row})

    def get_structure(self):
        return self.groups


class Warnings:
    def __init__(self):
        self.warnings = []

    def push_white(self, row: int, col: int, comment: str):
        self.warnings.append({'row': row, 'col': col, 'comment': comment})

    def get_warnings(self):
        return self.warnings


class Stat:
    def __init__(self, stmt=None):
        self.category = {}
        self.kpi_list = None
        if stmt:
            self._load_data(stmt)

    def _load_data(self, stmt):
        from .db_service import DBService
        from datetime import datetime

        kpi_data = DBService.get_kpi_plans_data(
            datetime.now().strftime('%Y-%m-01'),
            datetime.now().strftime('%Y-%m-%d')
        )
        self.kpi_list = OptimizedKPIList(kpi_data)

    def push_offer(self, sql_data: Dict):
        o = {
            'id': sql_data.get('id'),
            'name': sql_data.get('name'),
            'category_name': sql_data.get('category_name')
        }
        key_category = o['category_name']
        if key_category not in self.category:
            self.category[key_category] = CategoryItem(key_category, key_category)
        self.category[key_category].push_offer(o, sql_data)

    def push_lead(self, sql_data: Dict):
        l = {
            'offer_id': sql_data.get('offer_id'),
            'offer_name': sql_data.get('offer_name'),
            'aff_id': sql_data.get('aff_id'),
            'operator_name': sql_data.get('operator_name'),
            'category_name': sql_data.get('category_name')
        }
        key_category = l['category_name']
        if key_category not in self.category:
            self.category[key_category] = CategoryItem(key_category, key_category)
        self.category[key_category].push_lead(l, sql_data)

    def push_call(self, sql_data: Dict):
        c = {
            'offer_id': sql_data.get('offer_id'),
            'offer_name': sql_data.get('offer_name'),
            'aff_id': sql_data.get('aff_id'),
            'operator_name': sql_data.get('operator_name'),
            'category_name': sql_data.get('category_name')
        }
        key_category = c['category_name']
        if key_category not in self.category:
            self.category[key_category] = CategoryItem(key_category, key_category)
        self.category[key_category].push_call(c, sql_data)

    def finalyze(self):
        for category in self.category.values():
            category.finalyze(self.kpi_list)