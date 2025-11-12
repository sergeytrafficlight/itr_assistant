from typing import List, Dict, Any, Optional
from .statistics import safe_div


class Recommendation:
    """Класс рекомендации"""

    def __init__(self, value: Any, comment: str):
        self.value = value
        self.comment = comment


class RecommendationEngine:
    """Движок рекомендаций на основе google_kpi.txt"""

    def __init__(self, calls_count_for_analyze: int = 30):
        self.calls_count_for_analyze = calls_count_for_analyze

    def sort_to_array_operators(self, operators_dict: Dict[str, Any]) -> List[Any]:
        """Сортировка операторов по эффективности"""
        r1 = []
        r2 = []
        
        for operator in operators_dict.values():
            if (operator.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze and 
                operator.kpi_stat.effective_rate > 0.0):
                r1.append(operator)
            else:
                r2.append(operator)

        r1.sort(key=lambda x: x.kpi_stat.effective_rate)
        return r1 + r2

    def get_operators_for_recommendations(self, operators: List[Any]) -> Recommendation:
        """Получение операторов для рекомендаций"""
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

        result = []
        comment += f"Операторов для расчета эффективности: {eff_operators_count}\n--\n"
        
        calls = 0
        leads = 0
        for i, operator in enumerate(operators):
            if (len(result) < eff_operators_count and 
                operator.kpi_stat.effective_rate > 0.0 and 
                operator.kpi_stat.calls_group_effective_count > self.calls_count_for_analyze):
                result.append(operator.key)
                comment += f"\t{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"
                calls += operator.kpi_stat.calls_group_effective_count
                leads += operator.kpi_stat.leads_effective_count

        comment += f"--\nЗвонков: {calls} лидов: {leads}\n"
        comment += f"Результат: {safe_div(calls, leads)}\n"

        return Recommendation(result, comment)

    def get_recommended_efficiency(self, operators: List[Any], top_operators: Optional[List[str]]) -> Recommendation:
        """Получение рекомендуемой эффективности"""
        if top_operators is None:
            return Recommendation(None, "Недостаточно операторов для принятия решения")

        calls = 0
        leads = 0
        comment = ""

        for operator in operators:
            if operator.key not in top_operators:
                continue

            comment += f"\t{operator.key} звонков: {operator.kpi_stat.calls_group_effective_count} аппрувов: {operator.kpi_stat.leads_effective_count}\n"
            calls += operator.kpi_stat.calls_group_effective_count
            leads += operator.kpi_stat.leads_effective_count

        result = safe_div(calls, leads)
        comment += f"--\nЗвонков: {calls} лидов: {leads}\n"
        comment += f"Результат: {result}\n"

        if calls < self.calls_count_for_analyze:
            return Recommendation(None, comment + "Недостаточно звонков для принятия решения")
        else:
            return Recommendation(result, comment)

    def sort_operators_by_efficiency(self, operators_dict: Dict[str, Any]) -> List[Any]:
        """Сортировка операторов по эффективности"""
        return self.sort_to_array_operators(operators_dict)