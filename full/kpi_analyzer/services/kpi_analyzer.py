from .statistics import CallEfficiencyStat, LeadContainerStat, safe_div
from .recommendation_engine import RecommendationEngine, Recommendation
from datetime import datetime, date


class CommonItem:
    def __init__(self, key, description):
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

        self.kpi_stat = CallEfficiencyStat()
        self.lead_container = LeadContainerStat()
        self.kpi_current_plan = None
        self.recommended_effeciency = Recommendation(None, "")
        self.recommended_approve = None
        self.recommended_buyout = None
        self.recommended_confirmation_price = None

    def push_lead_container(self, sql_data):
        self.lead_container.push_lead(sql_data)

    def push_lead(self, sql_data):
        self.kpi_stat.push_lead(sql_data)

    def push_call(self, sql_data):
        self.kpi_stat.push_call(sql_data)

    def set_kpi_eff_need_correction(self, comment):
        self.kpi_eff_need_correction = True
        self.kpi_eff_need_correction_str = comment

    def set_kpi_app_need_correction(self, comment):
        self.kpi_app_need_correction = True
        self.kpi_app_need_correction_str = comment

    def set_kpi_buyout_need_correction(self, comment):
        self.kpi_buyout_need_correction = True
        self.kpi_buyout_need_correction_str = comment

    def set_confirmation_price_need_correction(self, comment):
        self.kpi_confirmation_price_need_correction = True
        self.kpi_confirmation_price_need_correction_str = comment

    def finalyze(self, kpi_list):
        self.kpi_stat.finalyze(kpi_list)
        self.lead_container.finalyze()
        self.kpi_operator_efficiency_fact = self.kpi_stat.effective_rate

        if self.kpi_current_plan and self.kpi_current_plan.operator_efficiency:
            self.kpi_stat.expecting_effective_rate = self.kpi_current_plan.operator_efficiency
        else:
            self.kpi_stat.expecting_effective_rate = 0.0

        if self.kpi_current_plan is not None:
            self.expecting_approve_leads = self.lead_container.leads_non_trash_count * self.kpi_current_plan.planned_approve
            self.expecting_buyout_leads = self.lead_container.leads_approved_count * self.kpi_current_plan.planned_buyout
        if self.kpi_current_plan and self.kpi_current_plan.planned_approve is not None:
            self.expecting_approve_leads = self.lead_container.leads_non_trash_count * self.kpi_current_plan.planned_approve
        else:
            self.expecting_approve_leads = 0

        if self.kpi_current_plan and self.kpi_current_plan.planned_buyout is not None:
            self.expecting_buyout_leads = self.lead_container.leads_non_trash_count * self.kpi_current_plan.planned_buyout
        else:
            self.expecting_buyout_leads = 0
        if self.kpi_current_plan is None:
            self.set_kpi_eff_need_correction("KPI не найден")
        elif self.recommended_effeciency.value is None:
            self.set_kpi_eff_need_correction("Не могу определить рекоммендацию")
        else:
            if abs(self.recommended_effeciency.value - self.kpi_current_plan.operator_efficiency) > 0.2:
                self.set_kpi_eff_need_correction(
                    f"Отличия в рек. эффективности и плановой более чем на 0.2, "
                    f"рек:{self.recommended_effeciency.value} план: {self.kpi_current_plan.operator_efficiency}"
                )
            elif (self.kpi_current_plan.operator_efficiency is None or
                  self.kpi_current_plan.operator_efficiency == "" or
                  self.kpi_current_plan.operator_efficiency == 0):
                self.set_kpi_eff_need_correction(
                    f"KPI эффективности не установлен '{self.kpi_current_plan.operator_efficiency}'")


class CategoryItem:
    def __init__(self, key, name, analysis_date):
        self.key = key
        self.description = name
        self.analysis_date = analysis_date
        self.offer = {}
        self.aff = {}
        self.operator = {}
        self.kpi_stat = CallEfficiencyStat()
        self.lead_container = LeadContainerStat()

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

        self.recommendation_engine = RecommendationEngine()

    def push_offer(self, offer_data, sql_data):
        offer_id = offer_data['id']
        if offer_id not in self.offer:
            self.offer[offer_id] = CommonItem(offer_id, offer_data['name'])

    def push_lead_container(self, lead_data, sql_data):
        offer_id = lead_data['offer_id']
        if offer_id not in self.offer:
            self.offer[offer_id] = CommonItem(offer_id, lead_data['offer_name'])

        self.offer[offer_id].push_lead_container(sql_data)
        self.lead_container.push_lead(sql_data)

    def push_lead(self, lead_data, sql_data):
        if lead_data['offer_id'] not in self.offer:
            self.offer[lead_data['offer_id']] = CommonItem(
                lead_data['offer_id'],
                lead_data['offer_name']
            )

        if lead_data['aff_id'] not in self.aff:
            self.aff[lead_data['aff_id']] = CommonItem(lead_data['aff_id'], "")

        if lead_data['operator_name'] not in self.operator:
            self.operator[lead_data['operator_name']] = CommonItem(
                lead_data['operator_name'],
                ""
            )

        self.offer[lead_data['offer_id']].push_lead(sql_data)
        self.aff[lead_data['aff_id']].push_lead(sql_data)
        self.operator[lead_data['operator_name']].push_lead(sql_data)
        self.kpi_stat.push_lead(sql_data)

    def push_call(self, call_data, sql_data):
        if call_data['offer_id'] not in self.offer:
            self.offer[call_data['offer_id']] = CommonItem(
                call_data['offer_id'],
                call_data['offer_name']
            )

        if call_data['aff_id'] not in self.aff:
            self.aff[call_data['aff_id']] = CommonItem(call_data['aff_id'], "")

        if call_data['operator_name'] not in self.operator:
            self.operator[call_data['operator_name']] = CommonItem(
                call_data['operator_name'],
                ""
            )

        self.offer[call_data['offer_id']].push_call(sql_data)
        self.aff[call_data['aff_id']].push_call(sql_data)
        self.operator[call_data['operator_name']].push_call(sql_data)
        self.kpi_stat.push_call(sql_data)

    def finalyze(self, kpi_list):
        self.kpi_stat.finalyze(kpi_list)
        self.lead_container.finalyze()

        analysis_date_str = self.analysis_date.strftime('%Y-%m-%d') if hasattr(self.analysis_date, 'strftime') else str(
            self.analysis_date)

        for operator in self.operator.values():
            operator.kpi_stat.finalyze(kpi_list)
            operator.lead_container.finalyze()

        self.operator_sorted = self.recommendation_engine.sort_operators_by_efficiency(self.operator)

        self.operator_recommended = self.recommendation_engine.get_operators_for_recommendations(
            self.operator_sorted
        )

        self.recommended_effeciency = self.recommendation_engine.get_recommended_efficiency(
            self.operator_sorted,
            self.operator_recommended.value
        )

        self.approve_percent_fact = safe_div(
            self.lead_container.leads_approved_count,
            self.lead_container.leads_non_trash_count
        ) * 100

        self.buyout_percent_fact = safe_div(
            self.lead_container.leads_buyout_count,
            self.lead_container.leads_approved_count
        ) * 100

        self.max_confirmation_price = 0

        for offer in self.offer.values():
            offer.kpi_current_plan = kpi_list.find_kpi(None, offer.key, analysis_date_str)
            offer.recommended_effeciency = self.recommended_effeciency
            offer.finalyze(kpi_list)

            if offer.kpi_current_plan is not None and offer.kpi_current_plan.confirmation_price is not None:
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
            self.approve_rate_plan = safe_div(
                self.expecting_approve_leads,
                self.lead_container.leads_non_trash_count
            )

            # ТОЧНОЕ СООТВЕТСТВИЕ ЭТАЛОНУ - всегда вычисляем perhaps_app_count
            if self.kpi_stat.effective_percent > 0:
                perhaps_app_count = ((self.lead_container.leads_approved_count / (
                        self.kpi_stat.effective_percent / 100))
                                     - self.lead_container.leads_approved_count) * 0.3 + self.lead_container.leads_approved_count
            else:
                perhaps_app_count = self.lead_container.leads_approved_count

            recommend_approve = safe_div(perhaps_app_count, self.lead_container.leads_non_trash_count) * 100

            comment = (f"Текущая эффективность: {self.kpi_stat.effective_percent}, "
                       f"коррекция -> вероятное к-во аппрувов: {perhaps_app_count}")

            if recommend_approve < self.approve_percent_fact:
                comment += (f"\nФактический аппрув ({self.approve_percent_fact}) "
                            f"выше рекоммендуемого ({recommend_approve}), коррекция рекоммендации до фактического аппрува")
                recommend_approve = self.approve_percent_fact
            elif recommend_approve > self.approve_percent_fact + 5:
                comment += (f"\nФактический аппрув ({self.approve_percent_fact}) "
                            f"рекоммендуемый ({recommend_approve}), выше на +5%, коррекция до верхней границы +5%")
                recommend_approve = self.approve_percent_fact + 5

            self.recommended_approve = Recommendation(recommend_approve, comment)

        if self.expecting_buyout_leads:
            self.buyout_rate_plan = safe_div(
                self.expecting_buyout_leads,
                self.lead_container.leads_approved_count
            )

        self.recommended_buyout = Recommendation(
            self.buyout_percent_fact * 1.02 if self.buyout_percent_fact else 0,
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
            elif (offer.kpi_current_plan.planned_approve is None or
                  offer.kpi_current_plan.planned_approve < 0.1):
                offer.set_kpi_app_need_correction(
                    f"KPI аппрува не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_approve}"
                )
            elif offer.recommended_approve.value is None:
                offer.set_kpi_app_need_correction("Рекоммендация несформирована")
            elif abs(offer.kpi_current_plan.planned_approve - offer.recommended_approve.value) > 1:
                offer.set_kpi_app_need_correction(
                    f"Плановый % аппрува ({offer.kpi_current_plan.planned_approve}) "
                    f"отличается от рекоммендации ({offer.recommended_approve.value}) более чем на 1%"
                )

            offer.recommended_buyout = self.recommended_buyout
            if offer.kpi_current_plan is None:
                offer.set_kpi_buyout_need_correction("KPI не найден")
            elif (offer.kpi_current_plan.planned_buyout is None or
                  offer.kpi_current_plan.planned_buyout < 0.1):
                offer.set_kpi_buyout_need_correction(
                    f"KPI выкупа не установлен или имеет предельно низкое значение (<0.1): {offer.kpi_current_plan.planned_buyout}"
                )
            elif offer.recommended_buyout.value is None:
                offer.set_kpi_buyout_need_correction("Рекоммендация несформирована")
            elif abs(offer.kpi_current_plan.planned_buyout - offer.recommended_buyout.value) > 1:
                offer.set_kpi_buyout_need_correction(
                    f"Плановый % выкупа ({offer.kpi_current_plan.planned_buyout}) "
                    f"отличается от рекоммендации ({offer.recommended_buyout.value}) более чем на 1%"
                )

            offer.recommended_confirmation_price = self.recommended_confirmation_price
            if offer.kpi_current_plan is None:
                offer.set_confirmation_price_need_correction("KPI не установлен")
            elif (offer.kpi_current_plan.confirmation_price is None or
                  offer.kpi_current_plan.confirmation_price < 1):
                offer.set_confirmation_price_need_correction("Чек подтверждения не установлен или предельно мал")
            elif self.max_confirmation_price == 0 or self.max_confirmation_price < 1:
                offer.set_confirmation_price_need_correction(
                    "Не удалось определить максимальный чек в группе или он предельно мал")
            elif offer.kpi_current_plan.confirmation_price != self.max_confirmation_price:
                offer.set_confirmation_price_need_correction(
                    f"Текущий чек подтверждения ({offer.kpi_current_plan.confirmation_price}) "
                    f"< Максимального в группе ({self.max_confirmation_price})"
                )

        for aff in self.aff.values():
            aff.kpi_stat.finalyze(kpi_list)
            aff.lead_container.finalyze()


class KpiPlan:
    def __init__(self, plan_data):
        self.id = plan_data.get('call_eff_kpi_id')
        self.period_date = plan_data.get('call_eff_period_date')
        self.offer_id = plan_data.get('call_eff_offer_id')
        self.affiliate_id = plan_data.get('call_eff_affiliate_id')
        self.operator_efficiency = plan_data.get('call_eff_operator_efficiency')
        self.planned_approve = plan_data.get('planned_approve_from')
        self.planned_buyout = plan_data.get('planned_buyout_from')
        self.confirmation_price = plan_data.get('confirmation_price')
        self.update_date = plan_data.get('updated_at')
        self.operator_effeciency_update_date = plan_data.get('operator_efficiency_updated_at')
        self.planned_approve_update_date = plan_data.get('planned_approve_update_at')
        self.planned_buyout_update_date = plan_data.get('planned_buyout_update_at')


class OptimizedKPIList:
    def __init__(self, kpi_plans_data):
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

    def find_kpi(self, affiliate_id, offer_id, date_str):
        return self.find_kpi_optimized(affiliate_id, offer_id, date_str)

    def find_kpi_optimized(self, affiliate_id, offer_id, date_str):
        if not date_str:
            return None

        date_str = str(date_str).split()[0]
        target_date = self._parse_date(date_str)
        if not target_date:
            return None

        date_key = str(target_date)
        date_candidates = self._date_index.get(date_key, [])

        if offer_id and str(offer_id).isdigit():
            for plan in date_candidates:
                if (str(plan.offer_id) == str(offer_id) and
                        (affiliate_id is None or str(plan.affiliate_id) == str(affiliate_id))):
                    return plan

        if offer_id and str(offer_id).isdigit():
            offer_candidates = self._offer_index.get(str(offer_id), [])

            nearest_plan = None
            min_diff = float('inf')

            for plan in offer_candidates:
                plan_date = self._parse_date(plan.period_date)
                if plan_date:
                    diff = abs((plan_date - target_date).days)
                    if diff < min_diff:
                        min_diff = diff
                        nearest_plan = plan

            if nearest_plan and min_diff <= 30:
                return nearest_plan

        if affiliate_id:
            for plan in date_candidates:
                if str(plan.affiliate_id) == str(affiliate_id):
                    return plan

        if date_candidates:
            return date_candidates[0]

        return None

    def _parse_date(self, date_str):
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

    def push_group(self, start_row, end_row):
        self.groups.append({'start': start_row, 'end': end_row})

    def get_structure(self):
        return self.groups


class Warnings:
    def __init__(self):
        self.warnings = []

    def push_white(self, row, col, comment):
        self.warnings.append({'row': row, 'col': col, 'comment': comment})

    def get_warnings(self):
        return self.warnings