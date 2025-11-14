from typing import List, Dict, Any, Optional
from .statistics import safe_div


class Recommendation:
    """Класс рекомендации"""
    def __init__(self, value: Any, comment: str):
        self.value = value
        self.comment = comment


class RecommendationEngine:
    """
    Движок рекомендаций — работает с EngineCallEfficiency2.Stat
    Эффективность = лиды / эффективные звонки
    """
    def __init__(self, calls_count_for_analyze: int = 30):
        self.calls_count_for_analyze = calls_count_for_analyze
        self.leads_count_for_analyze = 10

    def sort_operators_by_efficiency(self, operators_dict: Dict[str, Any]) -> List[Any]:
        """Сортировка операторов по эффективности (лиды / звонки)"""
        valid = []
        invalid = []
        for op in operators_dict.values():
            calls = op.kpi_stat.calls_group_effective_count
            leads = op.kpi_stat.leads_effective_count
            if (calls >= self.calls_count_for_analyze and leads >= self.leads_count_for_analyze):
                valid.append(op)
            else:
                invalid.append(op)
        # Сортировка по effective_rate = leads / calls
        valid.sort(key=lambda x: x.kpi_stat.effective_rate or 0.0, reverse=True)
        return valid + invalid

    def sort_offers_by_efficiency(self, offers_dict: Dict[str, Any]) -> List[Any]:
        return self.sort_operators_by_efficiency(offers_dict)

    def sort_affiliates_by_efficiency(self, affiliates_dict: Dict[str, Any]) -> List[Any]:
        return self.sort_operators_by_efficiency(affiliates_dict)

    def get_operators_for_recommendations(self, operators: List[Any]) -> Recommendation:
        """Выбор топ-операторов для расчёта эффективности"""
        valid_ops = [
            op for op in operators
            if (op.kpi_stat.effective_rate > 0.0 and
                op.kpi_stat.calls_group_effective_count >= self.calls_count_for_analyze)
        ]
        total_valid = len(valid_ops)
        comment = f"Операторов с достаточной статистикой: {total_valid}\n"

        target_count = max(min(round(total_valid * 0.4), 5), 3)
        if target_count < 3:
            return Recommendation(None, comment + "Недостаточно операторов для рекомендации")

        top_ops = valid_ops[:target_count]
        result_keys = [op.key for op in top_ops]

        calls = sum(op.kpi_stat.calls_group_effective_count for op in top_ops)
        leads = sum(op.kpi_stat.leads_effective_count for op in top_ops)

        comment += f"Выбрано для расчёта: {target_count}\n"
        for op in top_ops:
            rate = op.kpi_stat.effective_rate or 0.0
            comment += f" • {op.key}: {op.kpi_stat.calls_group_effective_count} зв. → {op.kpi_stat.leads_effective_count} лид. ({rate:.3f})\n"
        comment += f"ИТОГО: {calls} зв. → {leads} лид. = {safe_div(leads, calls):.3f}"

        return Recommendation(result_keys, comment)

    def get_recommended_efficiency(self, operators: List[Any], top_keys: Optional[List[str]]) -> Recommendation:
        """Расчёт рекомендуемой эффективности: лиды / звонки"""
        if not top_keys:
            return Recommendation(None, "Нет топ-операторов для расчёта")

        calls = 0
        leads = 0
        comment = "Расчёт по топ-операторам:\n"

        for op in operators:
            if op.key in top_keys:
                calls += op.kpi_stat.calls_group_effective_count
                leads += op.kpi_stat.leads_effective_count
                rate = op.kpi_stat.effective_rate or 0.0
                comment += f" • {op.key}: {op.kpi_stat.calls_group_effective_count} зв. → {op.kpi_stat.leads_effective_count} лид. ({rate:.3f})\n"

        if calls < self.calls_count_for_analyze:
            return Recommendation(None, comment + "\nНедостаточно звонков для рекомендации")

        result = safe_div(leads, calls)  # ← ЛИДЫ / ЗВОНКИ
        comment += f"ИТОГО: {calls} зв. → {leads} лид. = {result:.3f}"

        return Recommendation(result, comment)