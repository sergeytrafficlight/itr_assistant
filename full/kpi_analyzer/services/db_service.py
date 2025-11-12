from django.db import connections
from django.core.cache import cache
import logging
import time
from typing import Dict, List, Any
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)


class DBService:
    """Сервис для работы с базой данных на основе query_logic.txt - 100% ЭТАЛОННАЯ ЛОГИКА"""

    @staticmethod
    def exclude_category():
        return ['Архив', 'Входящая линия']

    @staticmethod
    def prepare_sql_array(values):
        """Подготовка массива для SQL запроса - ТОЧНО КАК В ЭТАЛОНЕ"""
        if not values:
            return ""
        if isinstance(values, str):
            values = [values]
        return ",".join([f"'{str(v).strip()}'" for v in values if v])

    @staticmethod
    def prepare_sql_array_array(values):
        """Подготовка массива массивов для SQL запроса - ТОЧНО КАК В ЭТАЛОНЕ"""
        return ",".join([f"'{str(v).strip()}'" for v in values])

    @staticmethod
    def normalize_datetime(datetime_str, time_part="00:00:00"):
        """Нормализация даты-времени - ТОЧНО КАК В ЭТАЛОНЕ"""
        if not datetime_str:
            return ""
        try:
            if " " in datetime_str:
                return datetime_str
            else:
                return f"{datetime_str} {time_part}"
        except Exception:
            return datetime_str

    @staticmethod
    def _convert_decimal_to_float(data):
        """Рекурсивно конвертирует Decimal в float"""
        if isinstance(data, dict):
            return {k: DBService._convert_decimal_to_float(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [DBService._convert_decimal_to_float(item) for item in data]
        elif isinstance(data, Decimal):
            return float(data)
        else:
            return data

    @staticmethod
    def get_kpi_query():
        """Получение запроса для KPI данных - ТОЧНО КАК В ЭТАЛОНЕ"""
        q = """SELECT
    offer_plan.id as call_eff_kpi_id,
    offer_plan.period_date as call_eff_period_date,
    offer_plan.offer_id as call_eff_offer_id,
    aff.external_id as call_eff_affiliate_id,
    offer_plan.operator_efficiency as call_eff_operator_efficiency,
    offer_plan.planned_approve_from as call_eff_planned_approve,
    offer_plan.planned_buyout_from as call_eff_planned_buyout,
    offer_plan.confirmation_price as call_eff_confirmation_price
FROM partners_tlofferplanneddataperiod AS offer_plan
LEFT JOIN partners_affiliate aff ON aff.id = offer_plan.affiliate_id
ORDER BY period_date ASC"""
        return q

    @staticmethod
    def get_offers(v: Dict) -> List[Dict]:
        """Получение списка офферов - ТОЧНО КАК В ЭТАЛОНЕ"""
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())

        q = """SELECT
    partners_offer.id as id,
    partners_offer.name as name,
    group_offer.name as category_name
FROM partners_offer
LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = partners_offer.id
LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
WHERE 1=1
AND group_offer.name NOT IN (""" + excl_category + """)"""

        if category_a:
            q += "AND group_offer.name IN (" + category_a + ")"
        if offer_a:
            q += "AND partners_offer.id IN (" + offer_a + ")\n"

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении офферов: {str(e)}")
            return []

    @staticmethod
    def get_lead(v: Dict) -> List[Dict]:
        """Получение данных по лидам - ТОЧНО КАК В ЭТАЛОНЕ"""
        date_from = DBService.normalize_datetime(v.get('date_from'), "00:00:00")
        date_to = DBService.normalize_datetime(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))

        q = """SELECT
    crm_leads_crmlead.id call_eff_crm_lead_id,
    LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) AS call_eff_approved_at,
    LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) AS call_eff_canceled_at,
    lv_op.username as lv_username,
    uu.id as call_eff_operator_id,
    lv_status.status_verbose as call_eff_status_verbose,
    lv_status.status_group as call_eff_status_group,
    offer.id as offer_id,
    offer.name as offer_name,
    group_offer.name as category_name,
    tl_lead.webmaster_id as aff_id
FROM partners_lvlead lv
LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
LEFT JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = lv.operator_id
LEFT JOIN users_user uu ON uu.id = pu.user_id
LEFT JOIN partners_lvleadstatuses AS lv_status ON lv.leadvertex_status_id = lv_status.id
LEFT JOIN partners_tllead AS tl_lead ON lv.tl_id = tl_lead.external_id
LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = tl_lead.subsystem_id
LEFT JOIN partners_offer as offer ON tl_lead.offer_id = offer.id
LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
WHERE 1=1
AND offer.id IS NOT NULL
AND lv_op.username IS NOT NULL
AND group_offer.name NOT IN (""" + excl_category + """)"""

        if category_a:
            q += "AND group_offer.name IN (" + category_a + ")"
        if date_from:
            q += "AND DATE_ADD(lv.approved_at, INTERVAL 3 HOUR) >= '" + date_from + "'\n"
        if date_to:
            q += "AND DATE_ADD(lv.approved_at, INTERVAL 3 HOUR) < '" + date_to + "'\n"
        if offer_a:
            q += "AND offer.id IN (" + offer_a + ")\n"
        if advertiser:
            q += "AND LOWER(subsystem.name) IN (" + advertiser + ")\n"
        if lv_op_a:
            q += "AND LOWER(lv_op.username) IN (" + lv_op_a + ")\n"
        if aff_id_a:
            q += "AND tl_lead.webmaster_id IN (" + aff_id_a + ")\n"

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении лидов: {str(e)}")
            return []

    @staticmethod
    def get_call(v: Dict) -> List[Dict]:
        """Получение данных по звонкам - ТОЧНО КАК В ЭТАЛОНЕ"""
        date_from = DBService.normalize_datetime(v.get('date_from'), "00:00:00")
        date_to = DBService.normalize_datetime(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))

        q = """SELECT
    partners_atscallevent.id as call_eff_id,
    crm_call_calldata.id as call_eff_crm_id,
    po.id as call_eff_offer_id,
    po.name as offer_name,
    partners_atscallevent.uniqueid as call_eff_uniqueid,
    LEFT(DATE_ADD(partners_atscallevent.calldate, INTERVAL 3 HOUR), 10) AS call_eff_calldate,
    crm_call_calldata.crm_lead_id as call_eff_crm_lead_id,
    uu.id as call_eff_operator_id,
    partners_atscallevent.billsec as call_eff_billsec,
    crm_call_calldata.oktell_duration as call_eff_billsec_exact,
    crm_call_calldata.oktell_anti_robot as call_eff_robo_detected,
    lv_op.username as lv_username,
    group_offer.name as category_name,
    pt.webmaster_id as call_eff_affiliate_id
FROM partners_atscallevent
LEFT JOIN crm_call_calldata ON crm_call_calldata.id = partners_atscallevent.assigned_call_data_id
LEFT JOIN partners_lvlead ON partners_atscallevent.lvlead_id = partners_lvlead.id
LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = partners_lvlead.id
LEFT JOIN partners_lvoperator lv_op ON lv_op.id = partners_atscallevent.lvoperator_id
LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = partners_atscallevent.lvoperator_id
LEFT JOIN users_user uu ON uu.id = pu.user_id
LEFT JOIN users_department ud ON ud.id = uu.department_id
LEFT JOIN partners_tllead pt ON partners_lvlead.tl_id = pt.external_id
LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
LEFT JOIN partners_offer po ON pt.offer_id = po.id
LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = po.id
LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
LEFT JOIN crm_call_oktelltask ON partners_atscallevent.oktell_task_id = crm_call_oktelltask.id
WHERE 1=1
AND partners_atscallevent.billsec >= 30
AND ((ud.name LIKE '%_НП_%' or ud.name LIKE '%_СП_%') or (crm_call_oktelltask.type = 'new_sales'))
AND po.id IS NOT null
AND lv_op.username IS NOT NULL
AND group_offer.name NOT IN (""" + excl_category + """)"""

        if category_a:
            q += "AND group_offer.name IN (" + category_a + ")"
        if date_from:
            q += "AND DATE_ADD(partners_atscallevent.calldate, INTERVAL 3 HOUR) >= '" + date_from + "'\n"
        if date_to:
            q += "AND DATE_ADD(partners_atscallevent.calldate, INTERVAL 3 HOUR) < '" + date_to + "'\n"
        if offer_a:
            q += "AND po.id IN (" + offer_a + ")\n"
        if advertiser:
            q += "AND LOWER(subsystem.name) IN (" + advertiser + ")\n"
        if lv_op_a:
            q += "AND LOWER(lv_op.username) IN (" + lv_op_a + ")\n"
        if aff_id_a:
            q += "AND pt.webmaster_id IN (" + aff_id_a + ")\n"

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении звонков: {str(e)}")
            return []

    @staticmethod
    def get_leads_container(v: Dict) -> List[Dict]:
        """Получение контейнера лидов - ТОЧНО КАК В ЭТАЛОНЕ"""
        date_from = DBService.normalize_datetime(v.get('date_from'), "00:00:00")
        date_to = DBService.normalize_datetime(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))

        q = """SELECT
    crm_leads_crmlead.id lead_container_crm_lead_id,
    crm_leads_crmlead.id call_eff_crm_lead_id,
    LEFT(DATE_ADD(lv.created_at, INTERVAL 3 HOUR), 19) lead_container_created_at,
    LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) lead_container_approved_at,
    LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) lead_container_canceled_at,
    LEFT(DATE_ADD(lv.buyout_at, INTERVAL 3 HOUR), 19) lead_container_buyout_at,
    lv_status.status_verbose as lead_container_status_verbose,
    lv_status.status_group as lead_container_status_group,
    pt.is_trash as lead_container_is_trash,
    LEFT(DATE_ADD(lv.created_at, INTERVAL 27 HOUR), 19) lead_container_lead_ttl_till,
    LEFT(DATE_ADD(NOW(), INTERVAL 3 HOUR), 19) as lead_container_now,
    offer.id as offer_id,
    offer.name as offer_name,
    pt.webmaster_id as aff_id,
    null as lv_username,
    group_offer.name as category_name
FROM partners_lvlead lv
LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
LEFT JOIN partners_tllead pt ON lv.tl_id = pt.external_id
LEFT JOIN partners_lvleadstatuses AS lv_status ON lv.leadvertex_status_id = lv_status.id
LEFT JOIN partners_offer as offer ON pt.offer_id = offer.id
LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
WHERE 1=1
AND offer.id IS NOT NULL
AND group_offer.name NOT IN (""" + excl_category + """)"""

        if category_a:
            q += "AND group_offer.name IN (" + category_a + ")"
        if date_from:
            q += "AND DATE_ADD(lv.created_at, INTERVAL 3 HOUR) >= '" + date_from + "'\n"
        if date_to:
            q += "AND DATE_ADD(lv.created_at, INTERVAL 3 HOUR) < '" + date_to + "'\n"
        if offer_a:
            q += "AND offer.id IN (" + offer_a + ")\n"
        if advertiser:
            q += "AND LOWER(subsystem.name) IN (" + advertiser + ")\n"
        if aff_id_a:
            q += "AND pt.webmaster_id IN (" + aff_id_a + ")\n"

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении контейнера лидов: {str(e)}")
            return []

    @staticmethod
    def get_kpi_plans_data(date_from: str, date_to: str) -> List[Dict]:
        """Получение данных KPI планов - ТОЧНО КАК В ЭТАЛОНЕ"""
        try:
            with connections['itrade'].cursor() as cursor:
                q = DBService.get_kpi_query()
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении KPI планов: {str(e)}")
            return []

    @staticmethod
    def get_calls_data_with_filters(filter_params: Dict) -> List[Dict]:
        """Получение данных звонков с фильтрами"""
        return DBService.get_call(filter_params)

    @staticmethod
    def get_leads_data_with_filters(filter_params: Dict) -> List[Dict]:
        """Получение данных лидов с фильтрами"""
        return DBService.get_lead(filter_params)

    @staticmethod
    def get_leads_container_data_with_filters(filter_params: Dict) -> List[Dict]:
        """Получение данных контейнера лидов с фильтрами"""
        return DBService.get_leads_container(filter_params)