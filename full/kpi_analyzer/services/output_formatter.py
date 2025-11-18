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

    # =============================================
    # 1. ДЛЯ GOOGLE SHEETS
    # =============================================
    def create_output_structure(self, stat) -> List[List[Any]]:
        pd = []
        headers = self._create_headers()
        pd.append(headers)
        for _ in range(13):
            self._fill_blank_pd(pd)

        categories = stat.get_categories_list()
        row_offset = 14
        grouper = {"groups": []}
        warnings = []

        for category in categories:
            if not self._should_include_category(category):
                continue

            self._fill_blank_pd(pd)
            category_row_idx = len(pd)
            self.print_pd_category(pd, category)

            # Офферы
            self._fill_blank_pd(pd, "Офферы")
            offer_start_row = len(pd)
            for offer in category.offer.values():
                if self._should_include_offer(offer):
                    self.print_pd_offer(pd, offer, category, offer_start_row, row_offset)

                    # Предупреждения
                    if offer.kpi_eff_need_correction:
                        warnings.append({
                            "row": len(pd),
                            "col": self.op.col_recommendation + 1,
                            "comment": offer.kpi_eff_need_correction_str
                        })
                    if offer.kpi_app_need_correction:
                        warnings.append({
                            "row": len(pd),
                            "col": self.op.col_approve_recommendation + 2,
                            "comment": offer.kpi_app_need_correction_str
                        })
                    if offer.kpi_buyout_need_correction:
                        warnings.append({
                            "row": len(pd),
                            "col": self.op.col_buyout_recommendation + 2,
                            "comment": offer.kpi_buyout_need_correction_str
                        })

            offer_end_row = len(pd) - 1

            # Операторы
            self._fill_blank_pd(pd, "Операторы")
            op_start = len(pd)
            for operator in category.operator.values():
                self.print_pd_operator(pd, operator)
            op_end = len(pd) - 1

            # Вебмастера
            self._fill_blank_pd(pd, "Вебмастера")
            aff_start = len(pd)
            for aff in category.aff.values():
                self.print_pd_aff(pd, aff)
            aff_end = len(pd) - 1

            # Группировка
            grouper["groups"].append({"start": offer_start_row, "end": offer_end_row})
            grouper["groups"].append({"start": op_start, "end": op_end})
            grouper["groups"].append({"start": aff_start, "end": aff_end})
            grouper["groups"].append({"start": category_row_idx, "end": len(pd) - 1})

        return pd, grouper["groups"], warnings

    def format_for_frontend(self, stat, group_rows: str = 'Нет') -> Dict[str, Any]:
        data = []
        groups = []
        recommendations = []
        current_row = 0

        for cat in stat.category.values():
            if not (cat.kpi_stat.calls_group_effective_count >= 5 or cat.lead_container.leads_non_trash_count >= 5):
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
                    'leads_non_trash_count': getattr(cat.lead_container, 'leads_non_trash_count', 0),
                    'leads_approved_count': getattr(cat.lead_container, 'leads_approved_count', 0),
                    'leads_buyout_count': getattr(cat.lead_container, 'leads_buyout_count', 0),
                },
                'approve_percent_fact': cat.approve_percent_fact,
                'approve_rate_plan': cat.approve_rate_plan,
                'buyout_percent_fact': cat.buyout_percent_fact,
                'offers': [],
                'operators': [],
                'affiliates': []
            }

            # Добавляем офферы
            for offer in cat.offer.values():
                if not (offer.kpi_stat.calls_group_effective_count >= 5 or getattr(offer.lead_container,
                                                                                   'leads_non_trash_count', 0) >= 5):
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
                    },
                    'lead_container': {
                        'leads_non_trash_count': getattr(offer.lead_container, 'leads_non_trash_count', 0),
                        'leads_approved_count': getattr(offer.lead_container, 'leads_approved_count', 0),
                        'leads_buyout_count': getattr(offer.lead_container, 'leads_buyout_count', 0),
                    },
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
                }
                cat_data['offers'].append(offer_data)

            # Добавляем операторов - ИСПРАВЛЕНО: используем description как имя оператора
            for operator in cat.operator.values():
                operator_data = {
                    'type': 'operator',
                    'key': operator.key,
                    'description': operator.description,  # Используем description вместо key для отображения имени
                    'kpi_stat': {
                        'calls_group_effective_count': operator.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': operator.kpi_stat.leads_effective_count,
                        'effective_percent': operator.kpi_stat.effective_percent,
                        'effective_rate': operator.kpi_stat.effective_rate,
                    },
                    'lead_container': {
                        'leads_non_trash_count': getattr(operator.lead_container, 'leads_non_trash_count', 0),
                        'leads_approved_count': getattr(operator.lead_container, 'leads_approved_count', 0),
                        'leads_buyout_count': getattr(operator.lead_container, 'leads_buyout_count', 0),
                    }
                }
                cat_data['operators'].append(operator_data)

            # Добавляем вебмастеров - ИСПРАВЛЕНО: используем description как имя вебмастера
            for affiliate in cat.aff.values():
                affiliate_data = {
                    'type': 'affiliate',
                    'key': affiliate.key,
                    'description': affiliate.description,  # Используем description вместо форматированной строки
                    'kpi_stat': {
                        'calls_group_effective_count': affiliate.kpi_stat.calls_group_effective_count,
                        'leads_effective_count': affiliate.kpi_stat.leads_effective_count,
                        'effective_percent': affiliate.kpi_stat.effective_percent,
                        'effective_rate': affiliate.kpi_stat.effective_rate,
                    },
                    'lead_container': {
                        'leads_non_trash_count': getattr(affiliate.lead_container, 'leads_non_trash_count', 0),
                        'leads_approved_count': getattr(affiliate.lead_container, 'leads_approved_count', 0),
                        'leads_buyout_count': getattr(affiliate.lead_container, 'leads_buyout_count', 0),
                    }
                }
                cat_data['affiliates'].append(affiliate_data)

            data.append(cat_data)
            current_row += 1  # категория — 1 строка

            # Подсчитываем общее количество строк для группировки
            total_rows_in_category = len(cat_data['offers']) + len(cat_data['operators']) + len(cat_data['affiliates'])
            if group_rows == 'Да' and total_rows_in_category > 0:
                groups.append({'start': group_start, 'end': group_start + total_rows_in_category})

            # Добавляем рекомендации
            if getattr(cat, 'recommended_efficiency', None) and cat.recommended_efficiency.value is not None:
                recommendations.append({
                    'type': 'efficiency',
                    'category': cat.description,
                    'current': round(cat.kpi_stat.effective_percent or 0, 1),
                    'recommended': round(cat.recommended_efficiency.value, 1),
                    'comment': cat.recommended_efficiency.comment
                })
            if getattr(cat, 'recommended_approve', None) and cat.recommended_approve.value is not None:
                recommendations.append({
                    'type': 'approve',
                    'category': cat.description,
                    'current': round(cat.approve_percent_fact or 0, 1),
                    'recommended': round(cat.recommended_approve.value, 1),
                    'comment': cat.recommended_approve.comment
                })

        return {
            'data': data,
            'groups': groups if group_rows == 'Да' else [],
            'recommendations': recommendations
        }

    def _create_headers(self) -> List[Any]:
        return [
            "Тип данных", "ID Оффер", "Оффер", "ID Вебмастер", "Оператор",
            "Ко-во звонков (эфф)", "Ко-во продаж (эфф)", "% эффективности", self.BLANK_KEY,
            "Эфф. факт", "Эфф. план", "Дата обновления", "Тип Плана", "Эфф. рекоммендация",
            "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "Ко-во лидов (без треша)", "Ко-во аппрувов", "% аппрува факт", "% аппрува план",
            "% аппрува рекоммендация", "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "% выкупа", "Ко-во выкупов", "% выкупа факт", "% выкупа план",
            "% выкупа рекоммендация", "Дата обновления", "Требуется коррекция",
            "[СВОД]", "Эфф. Рек.", "Коррекция?", "Апп. Рек.", "Коррекция?",
            "Чек Рек.", "Коррекция?", "Выкуп. Рек.", "Коррекция?", "Ссылка"
        ]

    def _fill_blank_pd(self, pd: List, label: str = None):
        row = [self.BLANK_KEY] * 43
        if label:
            row[0] = label
        pd.append(row)

    def _should_include_category(self, category: CategoryItem) -> bool:
        return (category.kpi_stat.calls_group_effective_count >= 5 or category.lead_container.leads_non_trash_count >= 5)

    def _should_include_offer(self, offer: OfferItem) -> bool:
        return (offer.kpi_stat.calls_group_effective_count >= 5 or offer.lead_container.leads_non_trash_count >= 5)

    def _cell_ref(self, row, col):
        col_letter = ""
        while col >= 0:
            col_letter = chr(ord('A') + (col % 26)) + col_letter
            col = col // 26 - 1
        return f"{col_letter}{row + 1}"

    def print_pd_category(self, pd: List, category: CategoryItem):
        row = [self.BLANK_KEY] * 43
        row[0] = self.ROW_TITLE_CATEGORY
        row[2] = category.description
        pd.append(row)

    def print_pd_offer(self, pd: List, offer: OfferItem, category: CategoryItem, offer_start_row: int, row_offset: int):
        row_idx = len(pd)
        row = [self.BLANK_KEY] * 43
        row[0] = self.ROW_TITLE_OFFER
        row[1] = offer.key
        row[2] = offer.description
        s = offer.kpi_stat
        row[5] = s.calls_group_effective_count
        row[6] = s.leads_effective_count
        calls_ref = self._cell_ref(row_idx, 5)
        leads_ref = self._cell_ref(row_idx, 6)
        row[7] = f"=ЭФФЕКТИВНОСТЬ({calls_ref},{leads_ref})"
        row[9] = self.gs.print_float(s.effective_rate)

        plan = offer.kpi_current_plan
        if plan:
            row[10] = self.gs.print_float(plan.operator_efficiency or 0)
            row[11] = plan.operator_efficiency_update_date or self.BLANK_KEY
            row[20] = self.gs.print_float(plan.planned_approve or 0)
            row[27] = self.gs.print_float(plan.planned_buyout or 0)
            row[22] = plan.planned_approve_update_date if plan else self.BLANK_KEY
            row[29] = plan.planned_buyout_update_date if plan else self.BLANK_KEY

        row[13] = self.gs.print_float(offer.recommended_efficiency.value or 0)
        if offer.kpi_eff_need_correction:
            row[15] = offer.kpi_eff_need_correction_str

        lc = offer.lead_container
        row[17] = lc.leads_non_trash_count
        row[18] = lc.leads_approved_count
        non_trash_ref = self._cell_ref(row_idx, 17)
        approved_ref = self._cell_ref(row_idx, 18)
        row[19] = f"=АППРУВ_ПРОЦЕНТ({approved_ref},{non_trash_ref})"
        if offer.recommended_approve:
            row[21] = self.gs.print_float(offer.recommended_approve.value or 0)
        if offer.kpi_app_need_correction:
            row[23] = offer.kpi_app_need_correction_str

        row[25] = lc.leads_buyout_count
        row[26] = f"=ВЫКУП_ПРОЦЕНТ({self._cell_ref(row_idx, 25)},{approved_ref})"
        if offer.recommended_buyout:
            row[28] = self.gs.print_float(offer.recommended_buyout.value or 0)
        if offer.kpi_buyout_need_correction:
            row[30] = offer.kpi_buyout_need_correction_str

        # СВОД
        row[32] = self.gs.print_float(offer.recommended_efficiency.value or 0)
        row[33] = "Да" if offer.kpi_eff_need_correction else ""
        row[34] = self.gs.print_float(offer.recommended_approve.value or 0) if offer.recommended_approve else ""
        row[35] = "Да" if offer.kpi_app_need_correction else ""
        row[36] = self.gs.print_float(offer.recommended_confirmation_price.value or 0) if offer.recommended_confirmation_price else ""
        row[37] = "Да" if offer.kpi_confirmation_price_need_correction else ""
        row[38] = self.gs.print_float(offer.recommended_buyout.value or 0) if offer.recommended_buyout else ""
        row[39] = "Да" if offer.kpi_buyout_need_correction else ""
        row[41] = f'=HYPERLINK("https://admin.crm.itvx.biz/partners/tloffer/{offer.key}/change/";"{offer.key}")'

        pd.append(row)

    def print_pd_operator(self, pd: List, operator: CommonItem):
        row_idx = len(pd)
        row = [self.BLANK_KEY] * 43
        row[0] = self.ROW_TITLE_OPERATOR
        row[4] = operator.key
        s = operator.kpi_stat
        row[5] = s.calls_group_effective_count
        row[6] = s.leads_effective_count
        row[7] = f"=ЭФФЕКТИВНОСТЬ({self._cell_ref(row_idx, 5)},{self._cell_ref(row_idx, 6)})"
        row[9] = self.gs.print_float(s.effective_rate)
        pd.append(row)

    def print_pd_aff(self, pd: List, aff: CommonItem):
        row_idx = len(pd)
        row = [self.BLANK_KEY] * 43
        row[0] = self.ROW_TITLE_AFF
        row[3] = aff.key
        s = aff.kpi_stat
        row[5] = s.calls_group_effective_count
        row[6] = s.leads_effective_count
        row[7] = f"=ЭФФЕКТИВНОСТЬ({self._cell_ref(row_idx, 5)},{self._cell_ref(row_idx, 6)})"
        row[9] = self.gs.print_float(s.effective_rate)
        pd.append(row)

    def format_for_excel(self, stat) -> List[List[Any]]:
        """Форматирует данные для Excel-выгрузки"""
        rows = []

        # Заголовки
        headers = [
            'Type', 'Category', 'Name', 'Approve Plan', 'Approve Fact', 'Approve Rec',
            'Buyout Plan', 'Buyout Fact', 'Buyout Rec', 'Efficiency Rec',
            'Confirmation Price', 'Needs Correction', 'Comment'
        ]
        rows.append(headers)

        # Данные по категориям и офферам
        for cat in stat.category.values():
            if not self._should_include_category(cat):
                continue

            # Категория
            rows.append([
                'category',
                cat.description,
                '',  # Name пустой для категории
                '',  # Approve Plan
                round(cat.approve_percent_fact or 0, 1),
                round(cat.recommended_approve.value or 0, 1) if cat.recommended_approve else '',
                '',  # Buyout Plan
                round(cat.buyout_percent_fact or 0, 1),
                round(cat.recommended_buyout.value or 0, 1) if cat.recommended_buyout else '',
                round(cat.recommended_efficiency.value or 0, 1) if cat.recommended_efficiency else '',
                cat.recommended_confirmation_price.value if cat.recommended_confirmation_price else '',
                '✅' if any([cat.recommended_efficiency, cat.recommended_approve, cat.recommended_buyout]) else '❌',
                getattr(cat.recommended_efficiency, 'comment', '') or getattr(cat.recommended_approve, 'comment', '')
            ])

            # Офферы в категории
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