class LegacyFilterProcessor:
    """Обработчик фильтров в точном соответствии с Google Apps Script эталоном"""

    @staticmethod
    def process_analytics_params(request_data):
        """Обработка параметров как в op_analyze_kpi_v2.vars_proceed()"""
        return {
            'sheetName': 'Анализ KPI',
            'date_from': request_data.get('date_from', ''),
            'date_to': request_data.get('date_to', ''),
            'group_rows': request_data.get('group_rows', 'Нет'),
            'advertiser': request_data.get('advertiser', '').lower(),
            'output': request_data.get('output', 'Все'),
            'aff_id': request_data.get('aff_id', ''),
            'category': request_data.get('category', '').lower(),
            'offer_id': request_data.get('offer_id', ''),
            'lv_op': request_data.get('lv_op', '').lower(),
            'col_recommendation': 18,
            'col_approve_recommendation': 25,
            'col_buyout_recommendation': 32,
            'range_full': 'C:AV',
            'range_start_row': 13,
            'range_start': 'C1',
        }

    @staticmethod
    def should_include_offer(offer, category, output_filter):
        """Точная реализация логики включения офферов как в эталоне"""
        if output_filter == 'Все':
            return True

        if output_filter == 'Есть активность':
            has_calls = offer.kpi_stat.calls_group_effective_count >= 5
            has_leads = category.lead_container.leads_non_trash_count >= 5
            return has_calls or has_leads

        return False

    @staticmethod
    def should_include_category(category, output_filter):
        """Точная реализация логики включения категорий как в эталоне"""
        if output_filter == 'Все':
            return True

        has_calls = category.kpi_stat.calls_group_effective_count > 0
        has_leads = category.lead_container.leads_non_trash_count > 0

        if output_filter == 'Есть активность':
            return has_calls or has_leads
        elif output_filter == '--':
            return has_calls or has_leads

        return False