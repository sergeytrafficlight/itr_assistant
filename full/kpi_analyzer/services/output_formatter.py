from typing import List, Dict, Any, Optional
from .kpi_analyzer import OpAnalyzeKPI, CategoryItem, OfferItem, CommonItem
from .compatibility import GoogleScriptCompatibility
from .statistics import safe_div
from .formula_engine import FormulaEngine
import logging

logger = logging.getLogger(__name__)


class KPIOutputFormatter:
    def __init__(self):
        self.op = OpAnalyzeKPI()
        self.gs = GoogleScriptCompatibility()
        self.engine = FormulaEngine()
        self.BLANK_KEY = self.gs.BLANK_KEY
        self.ROW_TITLE_CATEGORY = self.op.ROW_TITLE_CATEGORY
        self.ROW_TITLE_OFFER = self.op.ROW_TITLE_OFFER
        self.ROW_TITLE_OPERATOR = self.op.ROW_TITLE_OPERATOR
        self.ROW_TITLE_AFF = self.op.ROW_TITLE_AFF

    def create_output_structure(self, stat) -> List[List[Any]]:
        pd = []
        headers = self._create_headers()
        pd.append(headers)
        categories = stat.get_categories_list()

        for category in categories:
            if not self._should_include_category(category):
                continue

            self._add_category_row(pd, category)

            for offer in category.offer.values():
                if self._should_include_offer(offer):
                    self._add_offer_row(pd, offer, category)

            for operator in category.operator.values():
                self._add_operator_row(pd, operator)

            for aff in category.aff.values():
                self._add_affiliate_row(pd, aff)

        return pd

    def _create_headers(self) -> List[Any]:
        return [
            "Тип данных", "ID Оффер", "Оффер", "ID Вебмастер", "Оператор",
            "Ко-во звонков (эфф)", "Лиды сырые", "Лиды нон-треш", "Аппрувы", "Выкупы",
            "Продажи", "% эффективности", self.BLANK_KEY,
            "Эфф. факт", "Эфф. план", "Дата обновления", "Тип Плана", "Эфф. рекоммендация",
            "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "% аппрува факт", "% аппрува план", "% аппрува рекоммендация",
            "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "% выкупа факт", "% выкупа план", "% выкупа рекоммендация",
            "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "% треша", "% аппрув от сырых", "% выкуп от сырых", "% выкуп от нетреша",
            "[СВОД]", "Эфф. Рек.", "Коррекция?", "Апп. Рек.", "Коррекция?",
            "Чек Рек.", "Коррекция?", "Выкуп. Рек.", "Коррекция?", "Ссылка"
        ]

    def _add_category_row(self, pd: List, category: CategoryItem):
        row = [self.BLANK_KEY] * 46
        row[0] = self.ROW_TITLE_CATEGORY
        row[2] = category.description

        s = category.kpi_stat
        lc = category.lead_container

        row[5] = s.calls_group_effective_count
        row[6] = lc.leads_raw_count
        row[7] = lc.leads_non_trash_count
        row[8] = lc.leads_approved_count
        row[9] = lc.leads_buyout_count
        row[10] = s.leads_effective_count
        row[11] = s.effective_percent

        row[13] = s.effective_rate
        row[14] = s.expecting_effective_rate

        if category.recommended_efficiency:
            row[17] = category.recommended_efficiency.value
            row[37] = category.recommended_efficiency.value

        if category.recommended_approve:
            row[23] = category.recommended_approve.value
            row[39] = category.recommended_approve.value

        if category.recommended_buyout:
            row[29] = category.recommended_buyout.value
            row[43] = category.recommended_buyout.value

        if category.recommended_confirmation_price:
            row[41] = category.recommended_confirmation_price.value

        row[21] = category.approve_percent_fact
        row[27] = category.buyout_percent_fact
        row[33] = category.trash_percent
        row[34] = category.raw_to_approve_percent
        row[35] = category.raw_to_buyout_percent
        row[36] = category.non_trash_to_buyout_percent

        correction_flags = []
        if category.kpi_eff_need_correction:
            row[19] = category.kpi_eff_need_correction_str
            row[38] = "Да"
            correction_flags.append("Эффективность")
        if category.kpi_app_need_correction:
            row[25] = category.kpi_app_need_correction_str
            row[40] = "Да"
            correction_flags.append("Аппрув")
        if category.kpi_buyout_need_correction:
            row[31] = category.kpi_buyout_need_correction_str
            row[44] = "Да"
            correction_flags.append("Выкуп")

        if correction_flags:
            row[36] = f"Требует анализа: {', '.join(correction_flags)}"

        pd.append(row)

    def _add_offer_row(self, pd: List, offer: OfferItem, category: CategoryItem):
        row = [self.BLANK_KEY] * 46
        row[0] = self.ROW_TITLE_OFFER
        row[1] = offer.key
        row[2] = offer.description

        s = offer.kpi_stat
        lc = offer.lead_container

        row[5] = s.calls_group_effective_count
        row[6] = lc.leads_raw_count
        row[7] = lc.leads_non_trash_count
        row[8] = lc.leads_approved_count
        row[9] = lc.leads_buyout_count
        row[10] = s.leads_effective_count
        row[11] = s.effective_percent

        row[13] = s.effective_rate

        plan = offer.kpi_current_plan
        if plan:
            row[14] = self.gs.print_float(plan.operator_efficiency or 0)
            row[15] = plan.operator_efficiency_update_date or self.BLANK_KEY
            row[22] = self.gs.print_float(plan.planned_approve or 0)
            row[24] = plan.planned_approve_update_date or self.BLANK_KEY
            row[28] = self.gs.print_float(plan.planned_buyout or 0)
            row[30] = plan.planned_buyout_update_date or self.BLANK_KEY

        if offer.recommended_efficiency and offer.recommended_efficiency.value is not None:
            row[17] = self.gs.print_float(offer.recommended_efficiency.value)
            row[37] = self.gs.print_float(offer.recommended_efficiency.value)

        if offer.recommended_approve and offer.recommended_approve.value is not None:
            row[23] = self.gs.print_float(offer.recommended_approve.value)
            row[39] = self.gs.print_float(offer.recommended_approve.value)

        if offer.recommended_buyout and offer.recommended_buyout.value is not None:
            row[29] = self.gs.print_float(offer.recommended_buyout.value)
            row[43] = self.gs.print_float(offer.recommended_buyout.value)

        if offer.recommended_confirmation_price and offer.recommended_confirmation_price.value is not None:
            row[41] = self.gs.print_float(offer.recommended_confirmation_price.value)

        row[21] = offer.approve_percent_fact
        row[27] = offer.buyout_percent_fact
        row[33] = offer.trash_percent
        row[34] = offer.raw_to_approve_percent
        row[35] = offer.raw_to_buyout_percent
        row[36] = offer.non_trash_to_buyout_percent

        if offer.kpi_eff_need_correction:
            row[19] = offer.kpi_eff_need_correction_str
            row[38] = "Да"

        if offer.kpi_app_need_correction:
            row[25] = offer.kpi_app_need_correction_str
            row[40] = "Да"

        if offer.kpi_buyout_need_correction:
            row[31] = offer.kpi_buyout_need_correction_str
            row[44] = "Да"

        if offer.kpi_confirmation_price_need_correction:
            row[42] = "Да"

        row[45] = f'=HYPERLINK("https://admin.crm.itvx.biz/partners/tloffer/{offer.key}/change/";"{offer.key}")'

        pd.append(row)

    def _add_operator_row(self, pd: List, operator: CommonItem):
        row = [self.BLANK_KEY] * 46
        row[0] = self.ROW_TITLE_OPERATOR
        row[4] = operator.description

        s = operator.kpi_stat
        lc = operator.lead_container

        row[5] = s.calls_group_effective_count
        row[6] = lc.leads_raw_count
        row[7] = lc.leads_non_trash_count
        row[8] = lc.leads_approved_count
        row[9] = lc.leads_buyout_count
        row[10] = s.leads_effective_count
        row[11] = s.effective_percent

        row[13] = s.effective_rate

        if operator.recommended_efficiency and operator.recommended_efficiency.value is not None:
            row[17] = self.gs.print_float(operator.recommended_efficiency.value)
            row[37] = self.gs.print_float(operator.recommended_efficiency.value)

        if operator.recommended_approve and operator.recommended_approve.value is not None:
            row[23] = self.gs.print_float(operator.recommended_approve.value)
            row[39] = self.gs.print_float(operator.recommended_approve.value)

        if operator.recommended_buyout and operator.recommended_buyout.value is not None:
            row[29] = self.gs.print_float(operator.recommended_buyout.value)
            row[43] = self.gs.print_float(operator.recommended_buyout.value)

        row[21] = operator.approve_percent_fact
        row[27] = operator.buyout_percent_fact
        row[33] = operator.trash_percent
        row[34] = operator.raw_to_approve_percent
        row[35] = operator.raw_to_buyout_percent
        row[36] = operator.non_trash_to_buyout_percent

        if operator.kpi_eff_need_correction:
            row[19] = operator.kpi_eff_need_correction_str
            row[38] = "Да"

        if operator.kpi_app_need_correction:
            row[25] = operator.kpi_app_need_correction_str
            row[40] = "Да"

        if operator.kpi_buyout_need_correction:
            row[31] = operator.kpi_buyout_need_correction_str
            row[44] = "Да"

        pd.append(row)

    def _add_affiliate_row(self, pd: List, aff: CommonItem):
        row = [self.BLANK_KEY] * 46
        row[0] = self.ROW_TITLE_AFF
        row[3] = aff.key
        row[2] = aff.description

        s = aff.kpi_stat
        lc = aff.lead_container

        row[5] = s.calls_group_effective_count
        row[6] = lc.leads_raw_count
        row[7] = lc.leads_non_trash_count
        row[8] = lc.leads_approved_count
        row[9] = lc.leads_buyout_count
        row[10] = s.leads_effective_count
        row[11] = s.effective_percent

        row[13] = s.effective_rate

        if aff.recommended_efficiency and aff.recommended_efficiency.value is not None:
            row[17] = self.gs.print_float(aff.recommended_efficiency.value)
            row[37] = self.gs.print_float(aff.recommended_efficiency.value)

        if aff.recommended_approve and aff.recommended_approve.value is not None:
            row[23] = self.gs.print_float(aff.recommended_approve.value)
            row[39] = self.gs.print_float(aff.recommended_approve.value)

        if aff.recommended_buyout and aff.recommended_buyout.value is not None:
            row[29] = self.gs.print_float(aff.recommended_buyout.value)
            row[43] = self.gs.print_float(aff.recommended_buyout.value)

        row[21] = aff.approve_percent_fact
        row[27] = aff.buyout_percent_fact
        row[33] = aff.trash_percent
        row[34] = aff.raw_to_approve_percent
        row[35] = aff.raw_to_buyout_percent
        row[36] = aff.non_trash_to_buyout_percent

        if aff.kpi_eff_need_correction:
            row[19] = aff.kpi_eff_need_correction_str
            row[38] = "Да"

        if aff.kpi_app_need_correction:
            row[25] = aff.kpi_app_need_correction_str
            row[40] = "Да"

        if aff.kpi_buyout_need_correction:
            row[31] = aff.kpi_buyout_need_correction_str
            row[44] = "Да"

        pd.append(row)

    def _should_include_category(self, category: CategoryItem) -> bool:
        return (category.kpi_stat.calls_group_effective_count >= 3 or
                category.lead_container.leads_non_trash_count >= 3)

    def _should_include_offer(self, offer: OfferItem) -> bool:
        return (offer.kpi_stat.calls_group_effective_count >= 3 or
                offer.lead_container.leads_non_trash_count >= 3)

    def format_recommendations_for_analytics(self, recommendations: List[Dict]) -> List[Dict]:
        formatted_recs = []

        for rec in recommendations:
            if rec['type'] == 'efficiency':
                current_val = rec['current']
                recommended_val = rec['recommended']
                difference = recommended_val - current_val

                formatted_recs.append({
                    'type': 'Эффективность',
                    'category': rec['category'],
                    'current': f"{current_val:.2f}%",
                    'recommended': f"{recommended_val:.2f}%",
                    'difference': f"{difference:+.2f}%",
                    'comment': f"Рекомендуется изменить эффективность с {current_val:.2f}% до {recommended_val:.2f}% ({difference:+.2f}%)",
                    'priority': 'high' if abs(difference) > 5 else 'medium',
                    'icon': '📊'
                })
            elif rec['type'] == 'approve':
                current_val = rec['current']
                recommended_val = rec['recommended']
                difference = recommended_val - current_val

                formatted_recs.append({
                    'type': 'Аппрув',
                    'category': rec['category'],
                    'current': f"{current_val:.2f}%",
                    'recommended': f"{recommended_val:.2f}%",
                    'difference': f"{difference:+.2f}%",
                    'comment': f"Рекомендуется изменить процент аппрува с {current_val:.2f}% до {recommended_val:.2f}% ({difference:+.2f}%)",
                    'priority': 'high' if abs(difference) > 10 else 'medium',
                    'icon': '✅'
                })
            elif rec['type'] == 'buyout':
                current_val = rec['current']
                recommended_val = rec['recommended']
                difference = recommended_val - current_val

                formatted_recs.append({
                    'type': 'Выкуп',
                    'category': rec['category'],
                    'current': f"{current_val:.2f}%",
                    'recommended': f"{recommended_val:.2f}%",
                    'difference': f"{difference:+.2f}%",
                    'comment': f"Рекомендуется изменить процент выкупа с {current_val:.2f}% до {recommended_val:.2f}% ({difference:+.2f}%)",
                    'priority': 'high' if abs(difference) > 5 else 'medium',
                    'icon': '💰'
                })

        formatted_recs.sort(key=lambda x: 0 if x['priority'] == 'high' else 1)

        return formatted_recs

    def format_for_frontend(self, stat, group_rows: str = 'Нет') -> Dict[str, Any]:
        data = []
        groups = []
        recommendations = []
        current_row = 0

        for cat in stat.category.values():
            if not (cat.kpi_stat.calls_group_effective_count >= 3 or cat.lead_container.leads_non_trash_count >= 3):
                continue

            group_start = current_row
            cat_data = {
                'type': 'category',
                'key': cat.key,
                'description': cat.description,
                'kpi_stat': {
                    'calls_group_effective_count': cat.kpi_stat.calls_group_effective_count,
                    'leads_effective_count': cat.kpi_stat.leads_effective_count,
                    'effective_percent': cat.kpi_stat.effective_percent,
                    'effective_rate': cat.kpi_stat.effective_rate,
                    'expecting_effective_rate': cat.kpi_stat.expecting_effective_rate,
                },
                'lead_container': {
                    'leads_raw_count': getattr(cat.lead_container, 'leads_raw_count', 0),
                    'leads_non_trash_count': getattr(cat.lead_container, 'leads_non_trash_count', 0),
                    'leads_approved_count': getattr(cat.lead_container, 'leads_approved_count', 0),
                    'leads_buyout_count': getattr(cat.lead_container, 'leads_buyout_count', 0),
                    'leads_trash_count': getattr(cat.lead_container, 'leads_trash_count', 0),
                    'leads_total_count': getattr(cat.lead_container, 'leads_total_count', 0),
                },
                'approve_percent_fact': cat.approve_percent_fact,
                'buyout_percent_fact': cat.buyout_percent_fact,
                'trash_percent': cat.trash_percent,
                'raw_to_approve_percent': cat.raw_to_approve_percent,
                'raw_to_buyout_percent': cat.raw_to_buyout_percent,
                'non_trash_to_buyout_percent': cat.non_trash_to_buyout_percent,
                'approve_rate_plan': cat.approve_rate_plan,
                'buyout_rate_plan': cat.buyout_rate_plan,
                'max_confirmation_price': cat.max_confirmation_price,
                'expecting_approve_leads': cat.expecting_approve_leads,
                'expecting_buyout_leads': cat.expecting_buyout_leads,
                'recommended_efficiency': cat.recommended_efficiency.value if cat.recommended_efficiency else None,
                'recommended_approve': cat.recommended_approve.value if cat.recommended_approve else None,
                'recommended_buyout': cat.recommended_buyout.value if cat.recommended_buyout else None,
                'recommended_confirmation_price': cat.recommended_confirmation_price.value if cat.recommended_confirmation_price else None,
                'offers': [],
                'operators': [],
                'affiliates': [],
                'kpi_eff_need_correction': getattr(cat, 'kpi_eff_need_correction_str', ''),
                'kpi_app_need_correction': getattr(cat, 'kpi_app_need_correction_str', ''),
                'kpi_buyout_need_correction': getattr(cat, 'kpi_buyout_need_correction_str', ''),
                'needs_efficiency_correction': bool(getattr(cat, 'kpi_eff_need_correction_str', '')),
                'needs_approve_correction': bool(getattr(cat, 'kpi_app_need_correction_str', '')),
                'needs_buyout_correction': bool(getattr(cat, 'kpi_buyout_need_correction_str', '')),
            }

            for offer in cat.offer.values():
                if not (offer.kpi_stat.calls_group_effective_count >= 3 or getattr(offer.lead_container,
                                                                                   'leads_non_trash_count', 0) >= 3):
                    continue

                kpi_plan = offer.kpi_current_plan

                offer_data = {
                    'type': 'offer',
                    'key': offer.key,
                    'description': offer.description,
                    'kpi_stat': {
                        'calls_group_effective_count': offer.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': offer.kpi_stat.leads_effective_count,
                        'effective_percent': offer.kpi_stat.effective_percent,
                        'effective_rate': offer.kpi_stat.effective_rate,
                        'expecting_effective_rate': offer.kpi_stat.expecting_effective_rate,
                    },
                    'lead_container': {
                        'leads_raw_count': getattr(offer.lead_container, 'leads_raw_count', 0),
                        'leads_non_trash_count': getattr(offer.lead_container, 'leads_non_trash_count', 0),
                        'leads_approved_count': getattr(offer.lead_container, 'leads_approved_count', 0),
                        'leads_buyout_count': getattr(offer.lead_container, 'leads_buyout_count', 0),
                        'leads_trash_count': getattr(offer.lead_container, 'leads_trash_count', 0),
                        'leads_total_count': getattr(offer.lead_container, 'leads_total_count', 0),
                    },
                    'approve_percent_fact': offer.approve_percent_fact,
                    'buyout_percent_fact': offer.buyout_percent_fact,
                    'trash_percent': offer.trash_percent,
                    'raw_to_approve_percent': offer.raw_to_approve_percent,
                    'raw_to_buyout_percent': offer.raw_to_buyout_percent,
                    'non_trash_to_buyout_percent': offer.non_trash_to_buyout_percent,
                    'expecting_approve_leads': offer.expecting_approve_leads,
                    'expecting_buyout_leads': offer.expecting_buyout_leads,
                    'kpi_current_plan': {
                        'operator_efficiency': kpi_plan.operator_efficiency if kpi_plan else None,
                        'planned_approve': kpi_plan.planned_approve if kpi_plan else None,
                        'planned_buyout': kpi_plan.planned_buyout if kpi_plan else None,
                        'confirmation_price': kpi_plan.confirmation_price if kpi_plan else None,
                        'operator_efficiency_update_date': getattr(kpi_plan, 'operator_efficiency_update_date',
                                                                   None) if kpi_plan else None,
                        'planned_approve_update_date': getattr(kpi_plan, 'planned_approve_update_date',
                                                               None) if kpi_plan else None,
                        'planned_buyout_update_date': getattr(kpi_plan, 'planned_buyout_update_date',
                                                              None) if kpi_plan else None,
                    } if kpi_plan else None,
                    'recommended_efficiency': offer.recommended_efficiency.value if offer.recommended_efficiency else None,
                    'recommended_approve': offer.recommended_approve.value if offer.recommended_approve else None,
                    'recommended_buyout': offer.recommended_buyout.value if offer.recommended_buyout else None,
                    'recommended_confirmation_price': offer.recommended_confirmation_price.value if offer.recommended_confirmation_price else None,
                    'kpi_eff_need_correction': offer.kpi_eff_need_correction_str,
                    'kpi_app_need_correction': offer.kpi_app_need_correction_str,
                    'kpi_buyout_need_correction': offer.kpi_buyout_need_correction_str,
                    'kpi_confirmation_price_need_correction': offer.kpi_confirmation_price_need_correction_str,
                    'needs_efficiency_correction': bool(offer.kpi_eff_need_correction_str),
                    'needs_approve_correction': bool(offer.kpi_app_need_correction_str),
                    'needs_buyout_correction': bool(offer.kpi_buyout_need_correction_str),
                    'needs_confirmation_price_correction': bool(offer.kpi_confirmation_price_need_correction_str),
                }
                cat_data['offers'].append(offer_data)

            for operator in cat.operator.values():
                operator_data = {
                    'type': 'operator',
                    'key': operator.key,
                    'description': operator.description,
                    'kpi_stat': {
                        'calls_group_effective_count': operator.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': operator.kpi_stat.leads_effective_count,
                        'effective_percent': operator.kpi_stat.effective_percent,
                        'effective_rate': operator.kpi_stat.effective_rate,
                        'expecting_effective_rate': operator.kpi_stat.expecting_effective_rate,
                    },
                    'lead_container': {
                        'leads_raw_count': getattr(operator.lead_container, 'leads_raw_count', 0),
                        'leads_non_trash_count': getattr(operator.lead_container, 'leads_non_trash_count', 0),
                        'leads_approved_count': getattr(operator.lead_container, 'leads_approved_count', 0),
                        'leads_buyout_count': getattr(operator.lead_container, 'leads_buyout_count', 0),
                        'leads_trash_count': getattr(operator.lead_container, 'leads_trash_count', 0),
                        'leads_total_count': getattr(operator.lead_container, 'leads_total_count', 0),
                    },
                    'approve_percent_fact': operator.approve_percent_fact,
                    'buyout_percent_fact': operator.buyout_percent_fact,
                    'trash_percent': operator.trash_percent,
                    'raw_to_approve_percent': operator.raw_to_approve_percent,
                    'raw_to_buyout_percent': operator.raw_to_buyout_percent,
                    'non_trash_to_buyout_percent': operator.non_trash_to_buyout_percent,
                    'recommended_efficiency': operator.recommended_efficiency.value if operator.recommended_efficiency else None,
                    'recommended_approve': operator.recommended_approve.value if operator.recommended_approve else None,
                    'recommended_buyout': operator.recommended_buyout.value if operator.recommended_buyout else None,
                    'recommended_confirmation_price': operator.recommended_confirmation_price.value if operator.recommended_confirmation_price else None,
                    'kpi_eff_need_correction': getattr(operator, 'kpi_eff_need_correction_str', ''),
                    'kpi_app_need_correction': getattr(operator, 'kpi_app_need_correction_str', ''),
                    'kpi_buyout_need_correction': getattr(operator, 'kpi_buyout_need_correction_str', ''),
                    'needs_efficiency_correction': bool(getattr(operator, 'kpi_eff_need_correction_str', '')),
                    'needs_approve_correction': bool(getattr(operator, 'kpi_app_need_correction_str', '')),
                    'needs_buyout_correction': bool(getattr(operator, 'kpi_buyout_need_correction_str', '')),
                }
                cat_data['operators'].append(operator_data)

            for affiliate in cat.aff.values():
                affiliate_data = {
                    'type': 'affiliate',
                    'key': affiliate.key,
                    'description': affiliate.description,
                    'kpi_stat': {
                        'calls_group_effective_count': affiliate.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': affiliate.kpi_stat.leads_effective_count,
                        'effective_percent': affiliate.kpi_stat.effective_percent,
                        'effective_rate': affiliate.kpi_stat.effective_rate,
                        'expecting_effective_rate': affiliate.kpi_stat.expecting_effective_rate,
                    },
                    'lead_container': {
                        'leads_raw_count': getattr(affiliate.lead_container, 'leads_raw_count', 0),
                        'leads_non_trash_count': getattr(affiliate.lead_container, 'leads_non_trash_count', 0),
                        'leads_approved_count': getattr(affiliate.lead_container, 'leads_approved_count', 0),
                        'leads_buyout_count': getattr(affiliate.lead_container, 'leads_buyout_count', 0),
                        'leads_trash_count': getattr(affiliate.lead_container, 'leads_trash_count', 0),
                        'leads_total_count': getattr(affiliate.lead_container, 'leads_total_count', 0),
                    },
                    'approve_percent_fact': affiliate.approve_percent_fact,
                    'buyout_percent_fact': affiliate.buyout_percent_fact,
                    'trash_percent': affiliate.trash_percent,
                    'raw_to_approve_percent': affiliate.raw_to_approve_percent,
                    'raw_to_buyout_percent': affiliate.raw_to_buyout_percent,
                    'non_trash_to_buyout_percent': affiliate.non_trash_to_buyout_percent,
                    'recommended_efficiency': affiliate.recommended_efficiency.value if affiliate.recommended_efficiency else None,
                    'recommended_approve': affiliate.recommended_approve.value if affiliate.recommended_approve else None,
                    'recommended_buyout': affiliate.recommended_buyout.value if affiliate.recommended_buyout else None,
                    'recommended_confirmation_price': affiliate.recommended_confirmation_price.value if affiliate.recommended_confirmation_price else None,
                    'kpi_eff_need_correction': getattr(affiliate, 'kpi_eff_need_correction_str', ''),
                    'kpi_app_need_correction': getattr(affiliate, 'kpi_app_need_correction_str', ''),
                    'kpi_buyout_need_correction': getattr(affiliate, 'kpi_buyout_need_correction_str', ''),
                    'needs_efficiency_correction': bool(getattr(affiliate, 'kpi_eff_need_correction_str', '')),
                    'needs_approve_correction': bool(getattr(affiliate, 'kpi_app_need_correction_str', '')),
                    'needs_buyout_correction': bool(getattr(affiliate, 'kpi_buyout_need_correction_str', '')),
                }
                cat_data['affiliates'].append(affiliate_data)

            data.append(cat_data)
            current_row += 1

            total_rows_in_category = len(cat_data['offers']) + len(cat_data['operators']) + len(cat_data['affiliates'])
            if group_rows == 'Да' and total_rows_in_category > 0:
                groups.append({'start': group_start, 'end': group_start + total_rows_in_category})

            if getattr(cat, 'recommended_efficiency', None) and cat.recommended_efficiency.value is not None:
                recommendations.append({
                    'type': 'efficiency',
                    'category': cat.description,
                    'current': round(cat.kpi_stat.effective_percent or 0, 2),
                    'recommended': round(cat.recommended_efficiency.value, 2),
                    'comment': cat.recommended_efficiency.comment
                })
            if getattr(cat, 'recommended_approve', None) and cat.recommended_approve.value is not None:
                recommendations.append({
                    'type': 'approve',
                    'category': cat.description,
                    'current': round(cat.approve_percent_fact or 0, 2),
                    'recommended': round(cat.recommended_approve.value, 2),
                    'comment': cat.recommended_approve.comment
                })
            if getattr(cat, 'recommended_buyout', None) and cat.recommended_buyout.value is not None:
                recommendations.append({
                    'type': 'buyout',
                    'category': cat.description,
                    'current': round(cat.buyout_percent_fact or 0, 2),
                    'recommended': round(cat.recommended_buyout.value, 2),
                    'comment': cat.recommended_buyout.comment
                })

        formatted_recommendations = self.format_recommendations_for_analytics(recommendations)

        return {
            'data': data,
            'groups': groups if group_rows == 'Да' else [],
            'recommendations': formatted_recommendations
        }

    def format_for_excel(self, stat) -> List[List[Any]]:
        rows = []

        headers = [
            'Type', 'Category', 'Name', 'Approve Plan', 'Approve Fact', 'Approve Rec',
            'Buyout Plan', 'Buyout Fact', 'Buyout Rec', 'Efficiency Rec',
            'Confirmation Price', 'Needs Correction', 'Comment'
        ]
        rows.append(headers)

        for cat in stat.category.values():
            if not self._should_include_category(cat):
                continue

            rows.append([
                'category',
                cat.description,
                '',
                '',
                round(cat.approve_percent_fact or 0, 1),
                round(cat.recommended_approve.value or 0, 1) if cat.recommended_approve else '',
                '',
                round(cat.buyout_percent_fact or 0, 1),
                round(cat.recommended_buyout.value or 0, 1) if cat.recommended_buyout else '',
                round(cat.recommended_efficiency.value or 0, 1) if cat.recommended_efficiency else '',
                cat.recommended_confirmation_price.value if cat.recommended_confirmation_price else '',
                '✅' if any([cat.recommended_efficiency, cat.recommended_approve, cat.recommended_buyout]) else '❌',
                getattr(cat.recommended_efficiency, 'comment', '') or getattr(cat.recommended_approve, 'comment', '')
            ])

            for offer in cat.offer.values():
                if not self._should_include_offer(offer):
                    continue

                kpi_plan = offer.kpi_current_plan
                rows.append([
                    'offer',
                    cat.description,
                    offer.description,
                    round(kpi_plan.planned_approve or 0, 1) if kpi_plan else '',
                    round(safe_div(offer.lead_container.leads_approved_count,
                                   offer.lead_container.leads_non_trash_count) * 100, 1),
                    round(offer.recommended_approve.value or 0, 1) if offer.recommended_approve else '',
                    round(kpi_plan.planned_buyout or 0, 1) if kpi_plan else '',
                    round(safe_div(offer.lead_container.leads_buyout_count,
                                   offer.lead_container.leads_approved_count) * 100, 1),
                    round(offer.recommended_buyout.value or 0, 1) if offer.recommended_buyout else '',
                    round(offer.recommended_efficiency.value or 0, 1) if offer.recommended_efficiency else '',
                    offer.recommended_confirmation_price.value if offer.recommended_confirmation_price else '',
                    '✅' if any([offer.kpi_eff_need_correction, offer.kpi_app_need_correction,
                                offer.kpi_buyout_need_correction]) else '❌',
                    offer.kpi_eff_need_correction_str or offer.kpi_app_need_correction_str or offer.kpi_buyout_need_correction_str
                ])

        return rows