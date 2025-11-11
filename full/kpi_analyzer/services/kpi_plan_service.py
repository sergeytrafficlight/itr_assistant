from django.db import connections


class KpiPlanService:
    """Сервис для работы с KPI планами как в эталоне"""

    @staticmethod
    def find_kpi_plan_for_operator(operator_name, date_from, date_to, target_date):
        """ПОЛНАЯ ЛОГИКА ПОИСКА KPI ПЛАНОВ ДЛЯ ОПЕРАТОРА"""
        print(f"🔍 Поиск KPI плана для {operator_name} на {target_date}")

        try:
            with connections['itrade'].cursor() as cursor:
                # 🔥 ТОЧНЫЙ ЗАПРОС КАК В ЭТАЛОНЕ
                sql = """
                    SELECT DISTINCT
                        kpi.id as kpi_id,
                        kpi.offer_id as offer_id,
                        kpi.affiliate_id as affiliate_id, 
                        kpi.operator_efficiency as operator_efficiency,
                        kpi.planned_approve as planned_approve,
                        kpi.planned_buyout as planned_buyout,
                        kpi.confirmation_price as confirmation_price,
                        kpi.period_date as period_date
                    FROM partners_tlofferplanneddataperiod kpi
                    WHERE kpi.period_date = %s
                    AND kpi.offer_id IN (
                        SELECT DISTINCT tl_lead.offer_id
                        FROM partners_lvlead lv
                        JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id  
                        JOIN partners_tllead tl_lead ON lv.tl_id = tl_lead.external_id
                        WHERE LOWER(lv_op.username) = LOWER(%s)
                        AND DATE(lv.created_at) BETWEEN %s AND %s
                    )
                    LIMIT 1
                """

                cursor.execute(sql, [target_date, operator_name, date_from.split()[0], date_to.split()[0]])
                result = cursor.fetchone()

                if result:
                    print(f"✅ НАЙДЕН KPI план для {operator_name}")
                    return {
                        'call_eff_kpi_id': result[0],
                        'call_eff_offer_id': result[1],
                        'call_eff_affiliate_id': result[2],
                        'call_eff_operator_efficiency': result[3],
                        'planned_approve': result[4],
                        'planned_buyout': result[5],
                        'confirmation_price': result[6],
                        'call_eff_period_date': result[7]
                    }
                else:
                    print(f"❌ KPI план НЕ НАЙДЕН для {operator_name}")
                    return None

        except Exception as e:
            print(f"🔴 ОШИБКА поиска KPI плана: {e}")
            return None