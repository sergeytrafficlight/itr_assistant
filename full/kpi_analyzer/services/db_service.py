from django.db import connections
from django.core.cache import cache
import logging
import time

logger = logging.getLogger(__name__)


class DBService:

    @staticmethod
    def exclude_category():
        return ['Архив', 'Входящая линия']

    @staticmethod
    def prepare_sql_array(values):
        if not values:
            return ""
        if isinstance(values, str):
            values = [values]
        return ",".join([f"'{str(v).strip()}'" for v in values if v])

    @staticmethod
    def prepare_sql_array_array(values):
        return ",".join([f"'{str(v).strip()}'" for v in values])

    @staticmethod
    def normalize_datetime(datetime_str, time_part):
        if not datetime_str:
            return ""
        if ' ' in datetime_str:
            return datetime_str
        return f"{datetime_str} {time_part}"

    @staticmethod
    def get_kpi_plans_data(date_from, date_to):
        print(f"🔴 ВЫЗВАН get_kpi_plans_data: {date_from} - {date_to}")

        # ОЧИСТКА КЭША ПЕРЕД ЗАПРОСОМ
        cache_key = f"kpi_plans_{date_from}_{date_to}"
        cache.delete(cache_key)

        print(f"🟢 ВЫПОЛНЯЕМ SQL ЗАПРОС БЕЗ КЭША")
        logger.info(f"Кэш отключен для KPI планов {date_from}-{date_to}, запрос к БД")
        start_time = time.time()
        try:
            with connections['itrade'].cursor() as cursor:
                sql = """SELECT
offer_plan.id as kpi_id,
offer_plan.period_date as period_date,
offer_plan.offer_id as offer_id,
aff.external_id as affiliate_id,
offer_plan.operator_efficiency as operator_efficiency
FROM partners_tlofferplanneddataperiod AS offer_plan
LEFT JOIN partners_affiliate aff ON aff.id = offer_plan.affiliate_id
WHERE offer_plan.period_date BETWEEN %s AND %s
ORDER BY period_date ASC"""

                print(f"🟡 SQL ЗАПРОС ДЛЯ KPI:")
                print(sql)
                print(f"🟡 ПАРАМЕТРЫ: {date_from}, {date_to}")

                logger.info(f"SQL запрос для получения KPI:")
                logger.info(f"{sql}")
                logger.info(f"Параметры: date_from={date_from}, date_to={date_to}")

                cursor.execute(sql, [date_from, date_to])
                columns = [col[0] for col in cursor.description]
                plans = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # НЕ СОХРАНЯЕМ В КЭШ
                execution_time = time.time() - start_time
                print(f"🔵 ПОЛУЧЕНО {len(plans)} KPI ПЛАНОВ за {execution_time:.2f} секунд")
                logger.info(f"Получено {len(plans)} KPI планов за {execution_time:.2f} секунд")

                return plans

        except Exception as e:
            print(f"🔴 ОШИБКА: {str(e)}")
            logger.error(f"Ошибка при получении KPI планов из БД: {str(e)}")
            raise

    @staticmethod
    def get_operator_kpi_mapping(date_from, date_to):
        print(f"🔴 ВЫЗВАН get_operator_kpi_mapping: {date_from} - {date_to}")
        logger.info(f"Получение маппинга оператор -> KPI за период {date_from} - {date_to}")
        start_time = time.time()

        try:
            with connections['itrade'].cursor() as cursor:
                sql = """SELECT 
lv_op.username as operator_name,
kpi.offer_id as offer_id,
kpi.affiliate_id as affiliate_id,
kpi.operator_efficiency as operator_efficiency,
kpi.planned_approve_from as planned_approve,
kpi.planned_buyout_from as planned_buyout,
kpi.confirmation_price as confirmation_price,
COUNT(*) as activity_count
FROM partners_lvlead lv
JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
JOIN partners_tllead tl_lead ON lv.tl_id = tl_lead.external_id
JOIN partners_tlofferplanneddataperiod kpi ON (
    kpi.offer_id = tl_lead.offer_id 
    AND kpi.period_date = %s
)
WHERE DATE_ADD(lv.created_at, INTERVAL 3 HOUR) BETWEEN %s AND %s
GROUP BY lv_op.username, kpi.offer_id, kpi.affiliate_id, 
         kpi.operator_efficiency, kpi.planned_approve_from, 
         kpi.planned_buyout_from, kpi.confirmation_price
ORDER BY activity_count DESC"""

                print(f"🟡 SQL ЗАПРОС ДЛЯ МАППИНГА ОПЕРАТОР->KPI:")
                print(sql)
                print(f"🟡 ПАРАМЕТРЫ: {date_from}, {date_to}")

                logger.info(f"SQL запрос для получения маппинга оператор->KPI:")
                logger.info(f"{sql}")
                logger.info(f"Параметры: date_from={date_from}, date_to={date_to}")

                cursor.execute(sql, [date_to, date_from, date_to])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

                execution_time = time.time() - start_time
                print(f"🔵 ПОЛУЧЕНО {len(results)} МАППИНГОВ за {execution_time:.2f} секунд")
                logger.info(f"Получено {len(results)} маппингов оператор->KPI за {execution_time:.2f} секунд")
                return results

        except Exception as e:
            print(f"🔴 ОШИБКА: {str(e)}")
            logger.error(f"Ошибка при получении маппинга оператор->KPI: {str(e)}")
            return []

    @staticmethod
    def get_offers(v):
        print(f"🔴 ВЫЗВАН get_offers: {v}")
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

        print(f"🟡 SQL ЗАПРОС ДЛЯ ОФФЕРОВ:")
        print(q)

        logger.info(f"SQL запрос для получения офферов:")
        logger.info(f"{q}")

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                print(f"🔵 ПОЛУЧЕНО {len(results)} ОФФЕРОВ")
                logger.info(f"Получено {len(results)} офферов")
                return results
        except Exception as e:
            print(f"🔴 ОШИБКА: {str(e)}")
            logger.error(f"Ошибка при получении офферов: {str(e)}")
            return []

    @staticmethod
    def get_lead(v):
        print(f"🔴 ВЫЗВАН get_lead: {v}")
        date_from = DBService.normalize_datetime(v.get('date_from'), "00:00:00")
        date_to = DBService.normalize_datetime(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))

        q = """SELECT
crm_leads_crmlead.id as crm_lead_id,
LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) AS approved_at,
LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) AS canceled_at,
lv_op.username as operator_name,
uu.id as operator_id,
lv_status.status_verbose as status_verbose,
lv_status.status_group as status_group,
offer.id as offer_id,
offer.name as offer_name,
group_offer.name as category_name,
tl_lead.webmaster_id as affiliate_id
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
WHERE 1=1"""

        q += "AND offer.id IS NOT NULL\n"
        q += "AND lv_op.username IS NOT NULL\n"
        q += "AND group_offer.name NOT IN (" + excl_category + ")\n"

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

        print(f"🟡 SQL ЗАПРОС ДЛЯ ЛИДОВ:")
        print(q)

        logger.info(f"SQL запрос для получения лидов:")
        logger.info(f"{q}")

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                print(f"🔵 ПОЛУЧЕНО {len(results)} ЛИДОВ")
                logger.info(f"Получено {len(results)} лидов")
                return results
        except Exception as e:
            print(f"🔴 ОШИБКА: {str(e)}")
            logger.error(f"Ошибка при получении лидов: {str(e)}")
            return []

    @staticmethod
    def get_call(v):
        print(f"🔴 ВЫЗВАН get_call: {v}")
        date_from = DBService.normalize_datetime(v.get('date_from'), "00:00:00")
        date_to = DBService.normalize_datetime(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))

        q = """SELECT
partners_atscallevent.id as call_id,
crm_call_calldata.id as crm_call_id,
po.id as offer_id,
po.name as offer_name,
partners_atscallevent.uniqueid as uniqueid,
LEFT(DATE_ADD(partners_atscallevent.calldate, INTERVAL 3 HOUR), 10) AS calldate,
crm_call_calldata.crm_lead_id as crm_lead_id,
uu.id as operator_id,
partners_atscallevent.billsec as billsec,
crm_call_calldata.oktell_duration as billsec_exact,
crm_call_calldata.oktell_anti_robot as robo_detected,
lv_op.username as operator_name,
group_offer.name as category_name,
pt.webmaster_id as affiliate_id
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
AND ((ud.name LIKE '%%_НП_%%' or ud.name LIKE '%%_СП_%%') or (crm_call_oktelltask.type = 'new_sales'))
AND po.id IS NOT null"""
        q += "AND lv_op.username IS NOT NULL\n"
        q += "AND group_offer.name NOT IN (" + excl_category + ")\n"

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

        print(f"🟡 SQL ЗАПРОС ДЛЯ ЗВОНКОВ:")
        print(q)

        logger.info(f"SQL запрос для получения звонков:")
        logger.info(f"{q}")

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                print(f"🔵 ПОЛУЧЕНО {len(results)} ЗВОНКОВ")
                logger.info(f"Получено {len(results)} звонков")
                return results
        except Exception as e:
            print(f"🔴 ОШИБКА: {str(e)}")
            logger.error(f"Ошибка при получении звонков: {str(e)}")
            return []

    @staticmethod
    def get_leads_container(v):
        print(f"🔴 ВЫЗВАН get_leads_container: {v}")
        date_from = DBService.normalize_datetime(v.get('date_from'), "00:00:00")
        date_to = DBService.normalize_datetime(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))

        q = """SELECT
crm_leads_crmlead.id as crm_lead_id,
crm_leads_crmlead.id as call_eff_crm_lead_id,
LEFT(DATE_ADD(lv.created_at, INTERVAL 3 HOUR), 19) as created_at,
LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) as approved_at,
LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) as canceled_at,
LEFT(DATE_ADD(lv.buyout_at, INTERVAL 3 HOUR), 19) as buyout_at,
lv_status.status_verbose as status_verbose,
lv_status.status_group as status_group,
pt.is_trash as is_trash,
LEFT(DATE_ADD(lv.created_at, INTERVAL 27 HOUR), 19) as lead_ttl_till,
LEFT(DATE_ADD(NOW(), INTERVAL 3 HOUR), 19) as now_time,
offer.id as offer_id,
offer.name as offer_name,
pt.webmaster_id as affiliate_id,
null as operator_name,
group_offer.name as category_name
FROM partners_lvlead lv
LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
LEFT JOIN partners_tllead pt ON lv.tl_id = pt.external_id
LEFT JOIN partners_lvleadstatuses AS lv_status ON lv.leadvertex_status_id = lv_status.id
LEFT JOIN partners_offer as offer ON pt.offer_id = offer.id
LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id 
LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id 
LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
WHERE 1=1"""

        q += "AND offer.id IS NOT NULL\n"
        q += "AND group_offer.name NOT IN (" + excl_category + ")\n"

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

        print(f"🟡 SQL ЗАПРОС ДЛЯ КОНТЕЙНЕРА ЛИДОВ:")
        print(q)

        logger.info(f"SQL запрос для получения контейнера лидов:")
        logger.info(f"{q}")

        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                print(f"🔵 ПОЛУЧЕНО {len(results)} ЗАПИСЕЙ КОНТЕЙНЕРА ЛИДОВ")
                logger.info(f"Получено {len(results)} записей контейнера лидов")
                return results
        except Exception as e:
            print(f"🔴 ОШИБКА: {str(e)}")
            logger.error(f"Ошибка при получении контейнера лидов: {str(e)}")
            return []

    @staticmethod
    def create_kpi_list_from_db(date_from, date_to):
        print(f"🔴 ВЫЗВАН create_kpi_list_from_db: {date_from} - {date_to}")
        kpi_plans_data = DBService.get_kpi_plans_data(date_from, date_to)
        from .optimized_services import OptimizedKPIList
        return OptimizedKPIList(kpi_plans_data)