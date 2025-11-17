from typing import Dict, List, Optional, Any
from .statistics import safe_div


class Recommendation:
    def __init__(self, value, comment: str = ""):
        self.value = value
        self.comment = comment


class RecommendationEngine:
    def __init__(self, calls_count_for_analyze: int = 30):
        self.calls_count_for_analyze = calls_count_for_analyze

    def sort_operators_by_efficiency(self, operators: Dict[str, Any]) -> List[Any]:
        result1 = []
        result2 = []

        for operator in operators.values():
            if (operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze and
                    operator.kpi_stat.effective_rate > 0.0):
                result1.append(operator)
            else:
                result2.append(operator)

        result1.sort(key=lambda x: x.kpi_stat.effective_rate)
        return result1 + result2

    def get_operators_for_recommendations(self, operators: List[Any]) -> Recommendation:
        eff_operators = 0
        for operator in operators:
            if (operator.kpi_stat.effective_rate > 0.0 and
                    operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze):
                eff_operators += 1

        eff_operators = round(eff_operators * 0.4)
        if eff_operators < 3:
            return Recommendation(None, "Недостаточно операторов для расчета плана")
        if eff_operators > 5:
            eff_operators = 5

        result = []
        comment = f"Операторов для анализа всего: {eff_operators}\n"
        calls_total = 0
        leads_total = 0

        for i, operator in enumerate(operators):
            if len(result) >= eff_operators:
                break
            if (operator.kpi_stat.effective_rate > 0.0 and
                    operator.kpi_stat.calls_group_effective_count > self.calls_count_for_analyze):
                result.append(operator.key)
                calls_total += operator.kpi_stat.calls_group_effective_count
                leads_total += operator.kpi_stat.leads_effective_count
                comment += f"{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"

        comment += f"Звонков: {calls_total} лидов: {leads_total}\n"
        comment += f"Результат: {safe_div(calls_total, leads_total)}\n"

        return Recommendation(result, comment)

    def get_recommended_efficiency(self, operators: List[Any], top_operators: List[str]) -> Recommendation:
        if top_operators is None:
            return Recommendation(None, "Недостаточно операторов для принятия решения")

        calls_total = 0
        leads_total = 0
        comment = ""

        for operator in operators:
            if operator.key not in top_operators:
                continue
            calls_total += operator.kpi_stat.calls_group_effective_count
            leads_total += operator.kpi_stat.leads_effective_count
            comment += f"{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"

        result = safe_div(calls_total, leads_total)
        comment += f"Звонков: {calls_total} лидов: {leads_total}\n"
        comment += f"Результат: {result}\n"

        if calls_total < self.calls_count_for_analyze:
            return Recommendation(None, comment + "Недостаточно звонков для принятия решения")
        else:
            return Recommendation(result, comment)