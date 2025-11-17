from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import time
from types import SimpleNamespace

from .engine_call_efficiency2 import (
    KpiList, Stat as CallStat, push_lead_to_engine, push_call_to_engine,
    finalize_engine_stat
)
from .recommendation_engine import RecommendationEngine, Recommendation
from .statistics import safe_div
from .db_service import DBService

logger = logging.getLogger(__name__)


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

        # Инициализация lead_container
        self.lead_container = SimpleNamespace(
            leads_non_trash_count=0,
            leads_approved_count=0,
            leads_buyout_count=0
        )

    def push_lead(self, sql_data: Dict, offer_id: int = None):
        push_lead_to_engine(sql_data, offer_id, self.kpi_stat.stat)

    def push_call(self, sql_data: Dict):
        push_call_to_engine(sql_data, self.kpi_stat.stat)

    def finalize(self, kpi_list: KpiList):
        finalize_engine_stat(self.kpi_stat.stat, kpi_list)

        self.kpi_stat.calls_group_effective_count = self.kpi_stat.stat.calls_group_effective_count
        self.kpi_stat.leads_effective_count = self.kpi_stat.stat.leads_effective_count
        self.kpi_stat.effective_percent = self.kpi_stat.stat.effective_percent
        self.kpi_stat.effective_rate = self.kpi_stat.stat.effective_rate
        self.kpi_stat.expecting_effective_rate = self.kpi_stat.stat.expecting_effective_rate

        if self.kpi_current_plan is None:
            self.set_kpi_eff_need_correction("KPI not found")
        elif self.recommended_efficiency.value is None:
            self.set_kpi_eff_need_correction("Recommendation not generated")
        else:
            if abs(self.recommended_efficiency.value - self.kpi_current_plan.operator_efficiency) > 0.2:
                self.set_kpi_eff_need_correction(
                    f"Diff >0.2: rec={self.recommended_efficiency.value:.3f}, plan={self.kpi_current_plan.operator_efficiency:.3f}"
                )
            elif self.kpi_current_plan.operator_efficiency <= 0:
                self.set_kpi_eff_need_correction(f"KPI not set: {self.kpi_current_plan.operator_efficiency}")

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
        self.max_confirmation_price: float = 0
        self.expecting_approve_leads: Optional[float] = None
        self.expecting_buyout_leads: Optional[float] = None

        self.operator_sorted: List[CommonItem] = []
        self.operator_recommended: Recommendation = Recommendation(None, "")
        self.approve_rate_plan: float = 0.0
        self.buyout_rate_plan: float = 0.0

        # Инициализация lead_container для категории
        self.lead_container = SimpleNamespace(
            leads_non_trash_count=0,
            leads_approved_count=0,
            leads_buyout_count=0
        )

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
        operator_name = lead_data.get('lv_username', 'No operator')

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

        push_lead_to_engine(sql_data, int(offer_id) if str(offer_id).isdigit() else None, self.kpi_stat.stat)

    def push_call(self, call_data: Dict, sql_data: Dict):
        offer_id = call_data.get('call_eff_offer_id')
        aff_id = call_data.get('call_eff_affiliate_id')
        operator_name = call_data.get('lv_username', 'No operator')

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

        push_call_to_engine(sql_data, self.kpi_stat.stat)

    def finalize(self, kpi_list: KpiList):
        for item in list(self.offer.values()) + list(self.aff.values()) + list(self.operator.values()):
            item.finalize(kpi_list)

        finalize_engine_stat(self.kpi_stat.stat, kpi_list)

        self.kpi_stat.calls_group_effective_count = self.kpi_stat.stat.calls_group_effective_count
        self.kpi_stat.leads_effective_count = self.kpi_stat.stat.leads_effective_count
        self.kpi_stat.effective_percent = self.kpi_stat.stat.effective_percent
        self.kpi_stat.effective_rate = self.kpi_stat.stat.effective_rate
        self.kpi_stat.expecting_effective_rate = self.kpi_stat.stat.expecting_effective_rate

        self.operator_sorted = self.recommendation_engine.sort_operators_by_efficiency(self.operator)
        self.operator_recommended = self.recommendation_engine.get_operators_for_recommendations(self.operator_sorted)
        self.recommended_efficiency = self.recommendation_engine.get_recommended_efficiency(
            self.operator_sorted, self.operator_recommended.value
        )

        self.max_confirmation_price = 0
        self.expecting_approve_leads = 0.0
        self.expecting_buyout_leads = 0.0
        has_none = False

        # Расчет lead_container данных для категории
        total_non_trash = 0
        total_approved = 0
        total_buyout = 0

        for offer in self.offer.values():
            offer.kpi_current_plan = kpi_list.find_kpi(None, str(offer.key), datetime.now().strftime('%Y-%m-%d'))
            offer.recommended_efficiency = self.recommended_efficiency
            offer.finalize(kpi_list)

            if offer.kpi_current_plan and offer.kpi_current_plan.confirmation_price:
                self.max_confirmation_price = max(self.max_confirmation_price,
                                                  offer.kpi_current_plan.confirmation_price)

            if offer.expecting_approve_leads is not None:
                self.expecting_approve_leads += offer.expecting_approve_leads
            else:
                has_none = True

            if offer.expecting_buyout_leads is not None:
                self.expecting_buyout_leads += offer.expecting_buyout_leads
            else:
                has_none = True

            # Суммируем данные для категории
            total_non_trash += offer.lead_container.leads_non_trash_count
            total_approved += offer.lead_container.leads_approved_count
            total_buyout += offer.lead_container.leads_buyout_count

        # Обновляем lead_container для категории
        self.lead_container.leads_non_trash_count = total_non_trash
        self.lead_container.leads_approved_count = total_approved
        self.lead_container.leads_buyout_count = total_buyout

        # Расчет процентов для категории
        self.approve_percent_fact = safe_div(total_approved, total_non_trash) * 100 if total_non_trash > 0 else 0
        self.buyout_percent_fact = safe_div(total_buyout, total_approved) * 100 if total_approved > 0 else 0

        if has_none:
            self.expecting_approve_leads = None
            self.expecting_buyout_leads = None

        # ЭТАЛОННАЯ ЛОГИКА РАСЧЕТА recommended_approve
        fact_approve = self.approve_percent_fact or 0

        if self.expecting_approve_leads is not None and self.expecting_approve_leads > 0:
            if self.kpi_stat.effective_percent and self.kpi_stat.effective_percent > 0:
                # ТОЧНАЯ ФОРМУЛА ИЗ ЭТАЛОНА
                perhaps_app_count = ((self.kpi_stat.leads_effective_count / (self.kpi_stat.effective_percent / 100))
                                     - self.kpi_stat.leads_effective_count) * 0.3 + self.kpi_stat.leads_effective_count
            else:
                perhaps_app_count = self.kpi_stat.leads_effective_count

            rec_approve = safe_div(perhaps_app_count, self.kpi_stat.leads_effective_count) * 100
            comment = f"Текущая эффективность: {self.kpi_stat.effective_percent:.1f}%, коррекция -> вероятное к-во аппрувов: {perhaps_app_count:.0f}"

            # КОРРЕКЦИЯ КАК В ЭТАЛОНЕ
            if rec_approve < fact_approve:
                comment += f"\nФактический аппрув ({fact_approve:.1f}) выше рекоммендуемого ({rec_approve:.1f}), коррекция рекоммендации до фактического аппрува"
                rec_approve = fact_approve
            elif rec_approve > fact_approve + 5:
                comment += f"\nФактический аппрув ({fact_approve:.1f}) рекоммендуемый ({rec_approve:.1f}), выше на +5%, коррекция до верхней границы +5%"
                rec_approve = fact_approve + 5

            self.recommended_approve = Recommendation(rec_approve, comment)
        else:
            rec_approve = fact_approve
            comment = "Нет данных для расчета ожидаемых аппрувов"
            self.recommended_approve = Recommendation(rec_approve, comment)

        # ЛОГИКА recommended_buyout ИЗ ЭТАЛОНА
        self.recommended_buyout = Recommendation(
            self.buyout_percent_fact * 1.02 if self.buyout_percent_fact else 0,
            f"Текущий выкуп: {self.buyout_percent_fact or 0:.1f}%, поднимаем на 2%"
        )

        # ЛОГИКА recommended_confirmation_price ИЗ ЭТАЛОНА
        self.recommended_confirmation_price = Recommendation(
            self.max_confirmation_price,
            "Максимальный чек в группе"
        )

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

        # ТОЧНАЯ ЛОГИКА ВАЛИДАЦИИ ИЗ ЭТАЛОНА
        if (offer.kpi_current_plan.planned_approve is None or offer.kpi_current_plan.planned_approve < 0.1):
            offer.set_kpi_app_need_correction(
                f"KPI аппрува не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_approve}")
        elif offer.recommended_approve.value is None:
            offer.set_kpi_app_need_correction("Рекоммендация несформирована")
        elif abs(offer.kpi_current_plan.planned_approve - offer.recommended_approve.value) > 1:
            offer.set_kpi_app_need_correction(
                f"Плановый % аппрува ({offer.kpi_current_plan.planned_approve}) отличается от рекоммендации ({offer.recommended_approve.value}) более чем на 1%")

        if (offer.kpi_current_plan.planned_buyout is None or offer.kpi_current_plan.planned_buyout < 0.1):
            offer.set_kpi_buyout_need_correction(
                f"KPI выкупа не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_buyout}")
        elif offer.recommended_buyout.value is None:
            offer.set_kpi_buyout_need_correction("Рекоммендация несформирована")
        elif abs(offer.kpi_current_plan.planned_buyout - offer.recommended_buyout.value) > 1:
            offer.set_kpi_buyout_need_correction(
                f"Плановый % выкупа ({offer.kpi_current_plan.planned_buyout}) отличается от рекоммендации ({offer.recommended_buyout.value}) более чем на 1%")

        if (offer.kpi_current_plan.confirmation_price is None or offer.kpi_current_plan.confirmation_price < 1):
            offer.set_confirmation_price_need_correction("Чек подтверждения не установлен или предельно мал")
        elif self.max_confirmation_price == 0 or self.max_confirmation_price < 1:
            offer.set_confirmation_price_need_correction(
                "Не удалось определить максимальный чек в группе или он предельно мал")
        elif offer.kpi_current_plan.confirmation_price != self.max_confirmation_price:
            offer.set_confirmation_price_need_correction(
                f"Текущий чек подтверждения ({offer.kpi_current_plan.confirmation_price}) < Максимального в группе ({self.max_confirmation_price})")


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

    def _process_leads_container_data(self, filters: Dict):
        """Обработка данных из get_leads_container с проверкой фейковых аппрувов"""
        leads_container = DBService.get_leads_container(filters)
        self.leads_container_data = leads_container

        # Группируем лиды по категориям и офферам
        category_leads = {}
        offer_leads = {}

        for lead in leads_container:
            category_name = lead.get('category_name', 'No category')
            offer_id = str(lead.get('offer_id', ''))

            # Инициализация структур данных
            if category_name not in category_leads:
                category_leads[category_name] = {'non_trash': 0, 'approved': 0, 'buyout': 0}
            if offer_id not in offer_leads:
                offer_leads[offer_id] = {'non_trash': 0, 'approved': 0, 'buyout': 0}

            # Проверяем фейковые аппрувы/выкупы
            is_trash = lead.get('lead_container_is_trash', False)
            if not is_trash:
                category_leads[category_name]['non_trash'] += 1
                offer_leads[offer_id]['non_trash'] += 1

                # Проверяем валидность аппрува
                if lead.get('lead_container_approved_at'):
                    fake_approve_reason = DBService.is_fake_approve({
                        'status_verbose': lead.get('lead_container_status_verbose', ''),
                        'status_group': lead.get('lead_container_status_group', ''),
                        'approved_at': lead.get('lead_container_approved_at', ''),
                        'canceled_at': lead.get('lead_container_canceled_at', '')
                    })
                    if not fake_approve_reason:  # Валидный аппрув
                        category_leads[category_name]['approved'] += 1
                        offer_leads[offer_id]['approved'] += 1

                        # Проверяем валидность выкупа
                        if lead.get('lead_container_buyout_at'):
                            fake_buyout_reason = DBService.is_fake_buyout({
                                'status_group': lead.get('lead_container_status_group', ''),
                                'buyout_at': lead.get('lead_container_buyout_at', '')
                            })
                            if not fake_buyout_reason:  # Валидный выкуп
                                category_leads[category_name]['buyout'] += 1
                                offer_leads[offer_id]['buyout'] += 1

        # Обновляем lead_container для категорий и офферов
        for cat_name, cat_data in category_leads.items():
            if cat_name in self.category:
                self.category[cat_name].lead_container.leads_non_trash_count = cat_data['non_trash']
                self.category[cat_name].lead_container.leads_approved_count = cat_data['approved']
                self.category[cat_name].lead_container.leads_buyout_count = cat_data['buyout']

        for offer_id, offer_data in offer_leads.items():
            for category in self.category.values():
                if offer_id in category.offer:
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
            'offer_id': sql_data.get('call_eff_offer_id'),
            'offer_name': sql_data.get('offer_name', ''),
            'aff_id': sql_data.get('call_eff_affiliate_id'),
            'lv_operator': sql_data.get('lv_username', 'No operator')
        }
        self.category[cat_name].push_call(call_data, sql_data)

    def finalize(self, kpi_plans_data: List[Dict], filters: Dict):
        self._load_kpi_data(kpi_plans_data)
        # Обрабатываем данные контейнерных лидов с проверкой фейковых аппрувов
        self._process_leads_container_data(filters)
        for cat in self.category.values():
            cat.finalize(self.kpi_list)

    def get_categories_list(self) -> List[CategoryItem]:
        return list(self.category.values())


class OpAnalyzeKPI:
    # Константы для output_formatter
    ROW_TITLE_CATEGORY = "Категория"
    ROW_TITLE_OFFER = "Оффер"
    ROW_TITLE_OPERATOR = "Оператор"
    ROW_TITLE_AFF = "Вебмастер"

    col_recommendation = 13
    col_approve_recommendation = 21
    col_buyout_recommendation = 28

    def __init__(self):
        self.stat = Stat()

    def run_analysis(self, filters: Dict) -> Stat:
        logger.info(">>> Starting KPI analysis...")

        kpi_plans = DBService.get_kpi_plans_data()
        offers = DBService.get_offers(filters)
        leads = DBService.get_leads(filters)
        calls = DBService.get_calls(filters)

        for offer in offers:
            self.stat.push_offer(offer)
        for lead in leads:
            self.stat.push_lead(lead)
        for call in calls:
            self.stat.push_call(call)

        self.stat.finalize(kpi_plans, filters)
        return self.stat