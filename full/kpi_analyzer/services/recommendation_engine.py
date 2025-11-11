# kpi_analyzer/services/recommendation_engine.py
from .statistics import safe_div


class Recommendation:
    """Аналог op_analyze_kpi_v2.recommendation"""

    def __init__(self, value, comment):
        self.value = value
        self.comment = comment


class RecommendationEngine:
    """Движок рекомендаций для KPI"""

    def __init__(self, calls_count_for_analyze=30):
        self.calls_count_for_analyze = calls_count_for_analyze

    def get_operators_for_recommendations(self, operators):
        eff_operators = 0

        for operator in operators:
            if (operator.kpi_stat.effective_rate > 0.0 and
                    operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze):
                eff_operators += 1

        comment = f"Операторов для анализа всего: {eff_operators}\n"

        eff_operators_count = round(eff_operators * 0.4)
        if eff_operators_count < 3:
            return Recommendation(None, comment + f"Недостаточно операторов для расчета плана ({eff_operators_count})")

        if eff_operators_count > 5:
            eff_operators_count = 5

        top_operators = []
        total_calls = 0
        total_leads = 0

        comment += f"Операторов для расчета эффективности: {eff_operators_count}\n--\n"

        for operator in sorted(operators, key=lambda x: x.kpi_stat.effective_rate):
            if (len(top_operators) < eff_operators_count and
                    operator.kpi_stat.effective_rate > 0.0 and
                    operator.kpi_stat.calls_group_effective_count > self.calls_count_for_analyze):
                top_operators.append(operator.key)
                total_calls += operator.kpi_stat.calls_group_effective_count
                total_leads += operator.kpi_stat.leads_effective_count

                comment += (f"\t{operator.key} "
                            f"звонков: {operator.kpi_stat.calls_group_effective_count} "
                            f"аппрувов: {operator.kpi_stat.leads_effective_count}\n")

        comment += f"--\nЗвонков: {total_calls} лидов: {total_leads}\n"
        comment += f"Результат: {safe_div(total_calls, total_leads)}\n"

        return Recommendation(top_operators, comment)

    def get_recommended_efficiency(self, operators, top_operators):
        """Аналог op_analyze_kpi_v2.get_recommended_effeciency"""

        if top_operators is None:
            return Recommendation(None, "Недостаточно операторов для принятия решения")

        total_calls = 0
        total_leads = 0
        comment = ""

        for operator in operators:
            if operator.key not in top_operators:
                continue

            comment += (f"\t{operator.key} "
                        f"звонков: {operator.kpi_stat.calls_group_effective_count} "
                        f"аппрувов: {operator.kpi_stat.leads_effective_count}\n")

            total_calls += operator.kpi_stat.calls_group_effective_count
            total_leads += operator.kpi_stat.leads_effective_count

        result = safe_div(total_calls, total_leads)
        comment += f"--\nЗвонков: {total_calls} лидов: {total_leads}\n"
        comment += f"Результат: {result}\n"

        if total_calls < self.calls_count_for_analyze:
            return Recommendation(None, comment + "Недостаточно звонков для принятия решения")
        else:
            return Recommendation(result, comment)

    def sort_operators_by_efficiency(self, operators_dict):
        """Аналог op_analyze_kpi_v2.sort_to_array_operators"""
        effective_operators = []
        other_operators = []

        for key, operator in operators_dict.items():
            if (operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze and
                    operator.kpi_stat.effective_rate > 0.0):
                effective_operators.append(operator)
            else:
                other_operators.append(operator)

        # Сортируем по эффективности
        effective_operators.sort(key=lambda x: x.kpi_stat.effective_rate)
        return effective_operators + other_operators