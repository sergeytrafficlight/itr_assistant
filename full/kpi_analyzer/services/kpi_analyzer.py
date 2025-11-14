from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .engine_call_efficiency2 import EngineCallEfficiency2
from .recommendation_engine import RecommendationEngine, Recommendation
from .statistics import safe_div, GlobalLeadContainerStat

logger = logging.getLogger(__name__)

class KpiStat:
    def __init__(self):
        self.calls_group_effective_count = 0
        self.leads_effective_count = 0
        self.effective_percent = 0.0
        self.effective_rate = 0.0
        self.expecting_effective_rate = 0.0
        self.stat = EngineCallEfficiency2.Stat()

class CommonItem:
    def __init__(self, key: str, description: str):
        self.key = key
        self.description = description
        self.kpi_stat = KpiStat()
        self.lead_container = GlobalLeadContainerStat()
        self.kpi_current_plan: Optional[EngineCallEfficiency2.Kpi] = None
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

    def push_lead_container(self, sql_data: Dict):
        self.lead_container.push_lead(sql_data)

    def push_lead(self, sql_data: Dict, offer_id: int = None):
        EngineCallEfficiency2.push_lead_to_engine(sql_data, offer_id, self.kpi_stat)

    def push_call(self, sql_data: Dict):
        EngineCallEfficiency2.push_call_to_engine(sql_data, self.kpi_stat)

    def finalize(self, kpi_list: EngineCallEfficiency2.KpiList):
        EngineCallEfficiency2.finalize_engine_stat(self.kpi_stat, kpi_list)
        self.lead_container.finalize()

        if (self.kpi_current_plan and self.kpi_current_plan.planned_approve is not None
                and self.kpi_current_plan.planned_buyout is not None):
            self.expecting_approve_leads = (
                self.lead_container.leads_non_trash_count * self.kpi_current_plan.planned_approve
            )
            self.expecting_buyout_leads = (
                self.lead_container.leads_approved_count * self.kpi_current_plan.planned_buyout
            )
        else:
            self.expecting_approve_leads = None
            self.expecting_buyout_leads = None

        if self.kpi_current_plan is None:
            self.set_kpi_eff_need_correction("KPI not found")
        elif self.recommended_efficiency.value is None:
            self.set_kpi_eff_need_correction("Recommendation not generated")
        else:
            if abs(self.recommended_efficiency.value - self.kpi_current_plan.operator_efficiency) > 0.2:
                self.set_kpi_eff_need_correction(
                    f"Diff >0.2: rec={self.recommended_efficiency.value:.3f}, "
                    f"plan={self.kpi_current_plan.operator_efficiency:.3f}"
                )
            elif self.kpi_current_plan.operator_efficiency <= 0:
                self.set_kpi_eff_need_correction(
                    f"KPI not set: {self.kpi_current_plan.operator_efficiency}"
                )

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
        self.lead_container = GlobalLeadContainerStat()
        self.recommendation_engine = RecommendationEngine(calls_count_for_analyze=30)
        self.recommended_efficiency: Recommendation = Recommendation(None, "")
        self.recommended_approve: Recommendation = Recommendation(None, "")
        self.recommended_buyout: Recommendation = Recommendation(None, "")
        self.recommended_confirmation_price: Recommendation = Recommendation(None, "")
        self.approve_percent_fact: Optional[float] = None
        self.buyout_percent_fact: Optional[float] = None
        self.max_confirmation_price: float = 0
        self.expecting_approve_leads: Optional[float] = None
        self.expecting_buyout_leads: Optional[float] = None
        self.operator_sorted: List[CommonItem] = []
        self.operator_recommended: Recommendation = Recommendation(None, "")
        self.approve_rate_plan: float = 0.0
        self.buyout_rate_plan: float = 0.0
        self.efficiency_plan: float = 0.0

    def push_offer(self, offer_data: Dict, sql_data: Dict):
        offer_id = offer_data.get('id')
        if not offer_id or not str(offer_id).isdigit():
            return
        key = str(offer_id)
        if key not in self.offer:
            self.offer[key] = OfferItem(key, offer_data.get('name', ''))
        self.offer[key].push_lead_container(sql_data)

    def push_lead_container(self, lead_data: Dict, sql_data: Dict):
        offer_id = lead_data.get('offer_id')
        if str(offer_id).isdigit():
            key = str(offer_id)
            if key not in self.offer:
                self.offer[key] = OfferItem(key, lead_data.get('offer_name', ''))
            self.offer[key].push_lead_container(sql_data)
        self.lead_container.push_lead(sql_data)

    def push_lead(self, lead_data: Dict, sql_data: Dict):
        offer_id = lead_data.get('offer_id')
        aff_id = lead_data.get('aff_id')
        operator_name = lead_data.get('lv_operator', 'No operator')

        if str(offer_id).isdigit():
            key = str(offer_id)
            if key not in self.offer:
                self.offer[key] = OfferItem(key, lead_data.get('offer_name', ''))
            self.offer[key].push_lead(sql_data, offer_id=int(offer_id))

        if str(aff_id).isdigit():
            key = str(aff_id)
            if key not in self.aff:
                self.aff[key] = CommonItem(key, f"Web #{key}")
            self.aff[key].push_lead(sql_data, offer_id=int(offer_id))

        if operator_name:
            if operator_name not in self.operator:
                self.operator[operator_name] = CommonItem(operator_name, operator_name)
            self.operator[operator_name].push_lead(sql_data, offer_id=int(offer_id))

        EngineCallEfficiency2.push_lead_to_engine(sql_data, int(offer_id) if str(offer_id).isdigit() else None, self.kpi_stat)

    def push_call(self, call_data: Dict, sql_data: Dict):
        offer_id = call_data.get('offer_id')
        aff_id = call_data.get('aff_id')
        operator_name = call_data.get('lv_operator', 'No operator')

        if str(offer_id).isdigit():
            key = str(offer_id)
            if key not in self.offer:
                self.offer[key] = OfferItem(key, call_data.get('offer_name', ''))
            self.offer[key].push_call(sql_data)

        if str(aff_id).isdigit():
            key = str(aff_id)
            if key not in self.aff:
                self.aff[key] = CommonItem(key, f"Web #{key}")
            self.aff[key].push_call(sql_data)

        if operator_name:
            if operator_name not in self.operator:
                self.operator[operator_name] = CommonItem(operator_name, operator_name)
            self.operator[operator_name].push_call(sql_data)

        EngineCallEfficiency2.push_call_to_engine(sql_data, self.kpi_stat)

    def finalize(self, kpi_list: EngineCallEfficiency2.KpiList):
        for item in list(self.offer.values()) + list(self.aff.values()) + list(self.operator.values()):
            item.finalize(kpi_list)

        EngineCallEfficiency2.finalize_engine_stat(self.kpi_stat, kpi_list)
        self.lead_container.finalize()

        self.operator_sorted = self.recommendation_engine.sort_operators_by_efficiency(self.operator)
        self.operator_recommended = self.recommendation_engine.get_operators_for_recommendations(self.operator_sorted)
        self.recommended_efficiency = self.recommendation_engine.get_recommended_efficiency(
            self.operator_sorted, self.operator_recommended.value
        )

        self.approve_percent_fact = (
            safe_div(self.lead_container.leads_approved_count, self.lead_container.leads_non_trash_count) * 100
            if self.lead_container.leads_non_trash_count > 0 else 0.0
        )
        self.buyout_percent_fact = (
            safe_div(self.lead_container.leads_buyout_count, self.lead_container.leads_approved_count) * 100
            if self.lead_container.leads_approved_count > 0 else 0.0
        )

        self.max_confirmation_price = 0
        self.expecting_approve_leads = 0.0
        self.expecting_buyout_leads = 0.0
        has_none = False
        total_planned_approve = 0.0
        total_planned_buyout = 0.0
        total_planned_efficiency = 0.0
        total_calls_for_efficiency = 0

        for offer in self.offer.values():
            offer.kpi_current_plan = kpi_list.find_kpi(None, int(offer.key), datetime.now().strftime('%Y-%m-%d'))
            offer.recommended_efficiency = self.recommended_efficiency
            offer.finalize(kpi_list)

            if offer.kpi_current_plan and offer.kpi_current_plan.confirmation_price:
                self.max_confirmation_price = max(self.max_confirmation_price, offer.kpi_current_plan.confirmation_price)

            if offer.expecting_approve_leads is not None:
                self.expecting_approve_leads += offer.expecting_approve_leads
            else:
                has_none = True

            if offer.expecting_buyout_leads is not None:
                self.expecting_buyout_leads += offer.expecting_buyout_leads
            else:
                has_none = True

            if offer.kpi_current_plan:
                if offer.kpi_current_plan.planned_approve is not None:
                    total_planned_approve += offer.kpi_current_plan.planned_approve * offer.lead_container.leads_non_trash_count
                if offer.kpi_current_plan.planned_buyout is not None:
                    total_planned_buyout += offer.kpi_current_plan.planned_buyout * offer.lead_container.leads_approved_count
                if offer.kpi_current_plan.operator_efficiency is not None:
                    total_planned_efficiency += offer.kpi_current_plan.operator_efficiency * offer.kpi_stat.calls_group_effective_count
                total_calls_for_efficiency += offer.kpi_stat.calls_group_effective_count

        if has_none:
            self.expecting_approve_leads = None
            self.expecting_buyout_leads = None

        total_leads_non_trash = self.lead_container.leads_non_trash_count
        total_leads_approved = self.lead_container.leads_approved_count
        self.approve_rate_plan = safe_div(total_planned_approve, total_leads_non_trash) * 100 if total_leads_non_trash else 0.0
        self.buyout_rate_plan = safe_div(total_planned_buyout, total_leads_approved) * 100 if total_leads_approved else 0.0
        self.efficiency_plan = safe_div(total_planned_efficiency, total_calls_for_efficiency) if total_calls_for_efficiency else 0.0

        fact_approve = self.approve_percent_fact
        if (self.kpi_stat.leads_effective_count > 0 and self.lead_container.leads_non_trash_count > 0):
            rec_approve = safe_div(self.kpi_stat.leads_effective_count, self.lead_container.leads_non_trash_count) * 100
            comment = f"Eff: {self.kpi_stat.effective_percent:.1f}%"
            if rec_approve < fact_approve:
                comment += " fact higher"
                rec_approve = fact_approve
            elif rec_approve > fact_approve + 5:
                comment += " fact lower"
                rec_approve = fact_approve + 5
            self.recommended_approve = Recommendation(rec_approve, comment)
        else:
            rec_approve = fact_approve
            comment = ("No effective calls" if self.lead_container.leads_non_trash_count > 0 else "No data")
            self.recommended_approve = Recommendation(rec_approve, comment)

        self.recommended_buyout = Recommendation(
            self.buyout_percent_fact * 1.02 if self.buyout_percent_fact else 0,
            "+2% from fact"
        )
        self.recommended_confirmation_price = Recommendation(self.max_confirmation_price, "Max check")

        for offer in self.offer.values():
            offer.recommended_approve = self.recommended_approve
            offer.recommended_buyout = self.recommended_buyout
            offer.recommended_confirmation_price = self.recommended_confirmation_price
            self._validate_offer_kpi(offer)

    def _validate_offer_kpi(self, offer: OfferItem):
        if not offer.kpi_current_plan:
            offer.set_kpi_app_need_correction("KPI not found")
            offer.set_kpi_buyout_need_correction("KPI not found")
            offer.set_confirmation_price_need_correction("KPI not found")
            return

        if (offer.kpi_current_plan.planned_approve is None or offer.kpi_current_plan.planned_approve <= 0):
            offer.set_kpi_app_need_correction("planned_approve <= 0 or not set")
        elif offer.recommended_approve.value is None:
            offer.set_kpi_app_need_correction("No recommendation")
        elif abs(offer.kpi_current_plan.planned_approve - offer.recommended_approve.value) > 1:
            offer.set_kpi_app_need_correction(f"Diff >1%")

        if (offer.kpi_current_plan.planned_buyout is None or offer.kpi_current_plan.planned_buyout <= 0):
            offer.set_kpi_buyout_need_correction("planned_buyout <= 0 or not set")
        elif abs(offer.kpi_current_plan.planned_buyout - offer.recommended_buyout.value) > 1:
            offer.set_kpi_buyout_need_correction(f"Diff >1%")

        if (offer.kpi_current_plan.confirmation_price is None or
                offer.kpi_current_plan.confirmation_price != self.max_confirmation_price):
            offer.set_confirmation_price_need_correction("Check < max")

class Stat:
    def __init__(self):
        self.category: Dict[str, CategoryItem] = {}
        self.kpi_list: Optional[EngineCallEfficiency2.KpiList] = None

    def _load_kpi_data(self, kpi_plans_data: List[Dict]):
        self.kpi_list = EngineCallEfficiency2.KpiList()
        loaded_count = 0
        for plan in kpi_plans_data or []:
            try:
                self.kpi_list.push_kpi(plan)
                loaded_count += 1
            except Exception as e:
                logger.error(f"[KPI LOAD ERROR] {e} | data: {plan}")
        logger.info(f"[KPI LOADED] Total: {loaded_count} plans")

    def push_offer(self, sql_data: Dict):
        cat_name = sql_data.get('category_name', 'No category')
        if cat_name not in self.category:
            self.category[cat_name] = CategoryItem(cat_name, cat_name)
        offer_data = {'id': sql_data.get('id'), 'name': sql_data.get('name', '')}
        self.category[cat_name].push_offer(offer_data, sql_data)

    def push_lead_container(self, sql_data: Dict):
        cat_name = sql_data.get('category_name', 'No category')
        if cat_name not in self.category:
            self.category[cat_name] = CategoryItem(cat_name, cat_name)
        lead_data = {'offer_id': sql_data.get('offer_id'), 'offer_name': sql_data.get('offer_name', '')}
        self.category[cat_name].push_lead_container(lead_data, sql_data)

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
            'offer_id': sql_data.get('call_eff_offer_id'),
            'offer_name': sql_data.get('offer_name', ''),
            'aff_id': sql_data.get('call_eff_affiliate_id'),
            'lv_operator': sql_data.get('lv_username', 'No operator')
        }
        self.category[cat_name].push_call(call_data, sql_data)

    def finalize(self, kpi_plans_data: List[Dict]):
        logger.info(f"[KPI INPUT] Received {len(kpi_plans_data)} KPI records")
        if not kpi_plans_data:
            logger.warning("[KPI INPUT] kpi_plans_data is EMPTY!")
        else:
            sample = kpi_plans_data[0]
            logger.info(f"[KPI SAMPLE] offer={sample.get('call_eff_offer_id')}, "
                        f"aff={sample.get('call_eff_affiliate_id')}, "
                        f"date={sample.get('call_eff_period_date')}, "
                        f"eff={sample.get('call_eff_operator_efficiency')}")

        self._load_kpi_data(kpi_plans_data)
        for cat in self.category.values():
            cat.finalize(self.kpi_list)

    def get_categories_list(self) -> List[CategoryItem]:
        return list(self.category.values())

class OpAnalyzeKPI:
    calls_count_for_analyze = 30
    ROW_TITLE_CATEGORY = "Category"
    ROW_TITLE_OFFER = "Offer"
    ROW_TITLE_AFF = "Web"
    ROW_TITLE_OPERATOR = "Operator"

    def __init__(self):
        self.vars = None
        self.recommendation_engine = RecommendationEngine(calls_count_for_analyze=self.calls_count_for_analyze)

    def vars_proceed(self):
        return {
            'sheetName': 'KPI Analysis',
            'date_from': '',
            'date_to': '',
            'group_rows': 'No',
            'advertiser': '',
            'output': 'All',
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

__all__ = ['OpAnalyzeKPI', 'CategoryItem', 'OfferItem', 'CommonItem', 'Stat', 'KpiStat']