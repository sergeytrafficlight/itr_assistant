
from .compatibility import GoogleScriptCompatibility
from .statistics import safe_div


class KPIOutputFormatter:
    """Форматирование вывода точно как в Google Apps Script эталоне"""

    def __init__(self):
        self.gs = GoogleScriptCompatibility()
        self.BLANK_KEY = self.gs.BLANK_KEY

        self.ROW_TITLE_CATEGORY = "Категория"
        self.ROW_TITLE_OFFER = "Оффер"
        self.ROW_TITLE_AFF = "Веб"
        self.ROW_TITLE_OPERATOR = "Оператор"

    def create_output_structure(self, stat_data):
        """Создаем полную структуру вывода как в эталоне"""
        print(f"🔍 DEBUG: Получено категорий для форматирования: {len(stat_data)}")

        # 🔥 ДЕТАЛЬНАЯ ПРОВЕРКА ДАННЫХ
        if stat_data:
            first_category = stat_data[0]
            print(f"🔍 DEBUG: Первая категория: {first_category.get('key')}")
            print(f"🔍 DEBUG: KPI stat первой категории: {first_category.get('kpi_stat')}")
            print(f"🔍 DEBUG: Lead container первой категории: {first_category.get('lead_container')}")
            print(f"🔍 DEBUG: Офферы в первой категории: {len(first_category.get('offers', []))}")

            if first_category.get('offers'):
                first_offer = first_category['offers'][0]
                print(f"🔍 DEBUG: Первый оффер: {first_offer.get('key')}")
                print(f"🔍 DEBUG: KPI stat оффера: {first_offer.get('kpi_stat')}")
                print(f"🔍 DEBUG: KPI plan оффера: {first_offer.get('kpi_current_plan')}")

        pd = []

        headers = self._create_headers()
        pd.append(headers)
        print(f"DEBUG: Заголовки созданы: {len(headers)} колонок")

        for i in range(13):
            self._fill_blank_pd(pd)

        if not stat_data:
            print("DEBUG: Нет данных категорий для вывода!")
            return pd

        for i, category in enumerate(stat_data):
            print(f"DEBUG: Обработка категории {i}: {category.get('key', 'NO_KEY')}")
            print(f"DEBUG:   Офферов: {len(category.get('offers', []))}")
            print(f"DEBUG:   Операторов: {len(category.get('operators', []))}")

            if self._should_include_category(category):
                self._fill_blank_pd(pd)
                self.print_pd_category(pd, category)

                self._fill_blank_pd(pd, 'Операторы')
                for operator in category.get('operators', []):
                    self.print_pd_operator(pd, operator)

                self._fill_blank_pd(pd, 'Офферы')
                for offer in category.get('offers', []):
                    if self._should_include_offer(offer, category):
                        self.print_pd_offer(pd, offer, category)

                self._fill_blank_pd(pd, 'Вебмастера')
                for aff in category.get('affiliates', []):
                    self.print_pd_aff(pd, aff)
            else:
                print(f"DEBUG: Категория {category.get('key')} исключена по фильтру")

        print(f"DEBUG: Итоговый массив: {len(pd)} строк")
        return pd

    def _create_headers(self):
        return [
            "Тип данных", "Категория", "ID Оффер", "Оффер", "ID Вебмастер", "Оператор",
            "Ко-во звонков (эфф)", "Ко-во продаж (эфф)", "% эффективности", self.BLANK_KEY,
            "Эфф. факт", "Эфф. план", "Дата обновления", "Тип Плана", "Эфф. рекоммендация",
            "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "Ко-во лидов (без треша)", "Ко-во аппрувов", "% аппрува факт", "% аппрува план",
            "% аппрува рекоммендация", "Дата обновления", "Требуется коррекция", self.BLANK_KEY,
            "% выкупа", "Ко-во выкупов", "% выкупа факт", "% выкупа план", "% выкупа рекоммендация",
            "Дата обновления", "Требуется коррекция", "[СВОД]", "Эфф. Рек.", "Коррекция?",
            "Апп. Рек.", "Коррекция?", "Чек Рек.", "Коррекция?", "Выкуп. Рек.", "Коррекция?",
            "Ссылка"
        ]

    def _fill_blank_pd(self, pd, label=None):
        row = [self.BLANK_KEY] * 43
        if label:
            row[0] = label
        pd.append(row)

    def _should_include_category(self, category):
        kpi_stat = category.get('kpi_stat', {})
        lead_container = category.get('lead_container', {})

        has_calls = kpi_stat.get('calls_group_effective_count', 0) > 0
        has_leads = lead_container.get('leads_non_trash_count', 0) > 0

        return has_calls or has_leads

    def _should_include_offer(self, offer, category):
        kpi_stat = offer.get('kpi_stat', {})
        lead_container = category.get('lead_container', {})

        has_calls = kpi_stat.get('calls_group_effective_count', 0) >= 5
        has_leads = lead_container.get('leads_non_trash_count', 0) >= 5

        return has_calls or has_leads

    def print_pd_category(self, pd, category):
        row = [self.BLANK_KEY] * 43

        row[0] = self.ROW_TITLE_CATEGORY
        row[1] = category.get('key', '')

        kpi_stat = category.get('kpi_stat', {})
        lead_container = category.get('lead_container', {})
        recommendations = category.get('recommendations', {})

        row[6] = kpi_stat.get('calls_group_effective_count', 0) or 0
        row[7] = kpi_stat.get('leads_effective_count', 0) or 0
        row[8] = self.gs.print_float(kpi_stat.get('effective_percent', 0)) or "0"

        row[10] = self.gs.print_float(kpi_stat.get('effective_rate', 0)) or "0.00"
        row[11] = self.gs.print_float(kpi_stat.get('expecting_effective_rate', 0)) or "0.00"

        eff_recommendation = recommendations.get('efficiency', {})
        row[14] = self.gs.print_float(eff_recommendation.get('value')) or "0.00"

        row[18] = lead_container.get('leads_non_trash_count', 0) or 0
        row[19] = lead_container.get('leads_approved_count', 0) or 0

        approved_count = lead_container.get('leads_approved_count', 0) or 0
        non_trash_count = lead_container.get('leads_non_trash_count', 0) or 1
        row[20] = self.gs.print_percent("", approved_count, non_trash_count, "") or "0%"

        row[21] = f"{self.gs.print_float(category.get('approve_rate_plan', 0)) or '0'}%"

        app_recommendation = recommendations.get('approve', {})
        row[22] = self.gs.print_float(app_recommendation.get('value')) or "0"

        row[27] = lead_container.get('leads_buyout_count', 0) or 0
        row[28] = self.gs.print_float(category.get('buyout_percent_fact', 0)) or "0"

        row[29] = self.gs.print_float(category.get('buyout_rate_plan', 0)) or "0"

        buyout_recommendation = recommendations.get('buyout', {})
        row[30] = self.gs.print_float(buyout_recommendation.get('value')) or "0"

        row[34] = self.gs.print_float(eff_recommendation.get('value')) or "0.00"
        row[36] = self.gs.print_float(app_recommendation.get('value')) or "0"

        price_recommendation = recommendations.get('confirmation_price', {})
        row[38] = self.gs.print_float(price_recommendation.get('value')) or "0"
        row[40] = self.gs.print_float(buyout_recommendation.get('value')) or "0"

        pd.append(row)

    def print_pd_offer(self, pd, offer, category):
        row = [self.BLANK_KEY] * 43

        row[0] = self.ROW_TITLE_OFFER
        row[1] = category.get('key', '')
        row[2] = offer.get('key', '')
        row[3] = offer.get('description', '')

        kpi_stat = offer.get('kpi_stat', {})
        lead_container = offer.get('lead_container', {})
        corrections = offer.get('corrections', {})

        row[6] = kpi_stat.get('calls_group_effective_count', 0) or 0
        row[7] = kpi_stat.get('leads_effective_count', 0) or 0
        row[8] = self.gs.print_float(kpi_stat.get('effective_percent', 0)) or "0"

        row[10] = self.gs.print_float(kpi_stat.get('effective_rate', 0)) or "0.00"

        kpi_plan = offer.get('kpi_current_plan', {})
        row[11] = self.gs.print_float(kpi_plan.get('operator_efficiency', 0)) or "0.00"
        row[12] = kpi_plan.get('operator_effeciency_update_date', self.BLANK_KEY)

        eff_recommendation = offer.get('recommended_effeciency', {})
        row[14] = self.gs.print_float(eff_recommendation.get('value')) or "0.00"
        row[15] = kpi_plan.get('operator_effeciency_update_date', self.BLANK_KEY)
        row[16] = corrections.get('efficiency', '')

        row[18] = lead_container.get('leads_non_trash_count', 0) or 0
        row[19] = lead_container.get('leads_approved_count', 0) or 0

        approved_count = lead_container.get('leads_approved_count', 0) or 0
        non_trash_count = lead_container.get('leads_non_trash_count', 0) or 1
        row[20] = self.gs.print_percent("", approved_count, non_trash_count, "") or "0%"

        row[21] = self.gs.print_float(kpi_plan.get('planned_approve', 0)) or "0"

        app_recommendation = offer.get('recommended_approve', {})
        row[22] = self.gs.print_float(app_recommendation.get('value')) or "0"
        row[23] = kpi_plan.get('planned_approve_update_date', self.BLANK_KEY)
        row[24] = corrections.get('approve', '')

        row[29] = self.gs.print_float(kpi_plan.get('planned_buyout', 0)) or "0"

        buyout_recommendation = offer.get('recommended_buyout', {})
        row[30] = self.gs.print_float(buyout_recommendation.get('value')) or "0"
        row[31] = kpi_plan.get('planned_buyout_update_date', self.BLANK_KEY)
        row[32] = corrections.get('buyout', '')

        row[34] = self.gs.print_float(eff_recommendation.get('value')) or "0.00"
        row[35] = corrections.get('efficiency', '')
        row[36] = self.gs.print_float(app_recommendation.get('value')) or "0"
        row[37] = corrections.get('approve', '')

        price_recommendation = offer.get('recommended_confirmation_price', {})
        row[38] = self.gs.print_float(price_recommendation.get('value')) or "0"
        row[39] = corrections.get('confirmation_price', '')
        row[40] = self.gs.print_float(buyout_recommendation.get('value')) or "0"
        row[41] = corrections.get('buyout', '')

        offer_key = offer.get('key', '')
        if offer_key and str(offer_key).isdigit():
            row[42] = f'=HYPERLINK("https://admin.crm.itvx.biz/partners/tloffer/{offer_key}/change/";"{offer_key}")'

        pd.append(row)

    def print_pd_operator(self, pd, operator):
        row = [self.BLANK_KEY] * 43

        row[0] = self.ROW_TITLE_OPERATOR
        row[5] = operator.get('key', '')

        kpi_stat = operator.get('kpi_stat', {})

        row[6] = kpi_stat.get('calls_group_effective_count', 0) or 0
        row[7] = kpi_stat.get('leads_effective_count', 0) or 0
        row[8] = self.gs.print_float(kpi_stat.get('effective_percent', 0)) or "0"
        row[10] = self.gs.print_float(kpi_stat.get('effective_rate', 0)) or "0.00"

        pd.append(row)

    def print_pd_aff(self, pd, aff):
        row = [self.BLANK_KEY] * 43

        row[0] = self.ROW_TITLE_AFF
        row[4] = aff.get('key', '')

        kpi_stat = aff.get('kpi_stat', {})

        row[6] = kpi_stat.get('calls_group_effective_count', 0) or 0
        row[7] = kpi_stat.get('leads_effective_count', 0) or 0
        row[8] = self.gs.print_float(kpi_stat.get('effective_percent', 0)) or "0"
        row[10] = self.gs.print_float(kpi_stat.get('effective_rate', 0)) or "0.00"

        pd.append(row)