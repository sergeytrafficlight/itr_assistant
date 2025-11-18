from django.db import connections
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class DBService:
    EXCLUDED_CATEGORIES = ['Архив', 'Входящая линия']

    BAD_APPROVE_STATUS = [
        'отправить позже', 'отмен', 'предоплаты', '4+ дней', '4 день', '3 день', '2 день', '1 день', 'перезвон'
    ]
    GOOD_APPROVE_STATUS_GROUP = ['accepted', 'shipped', 'paid', 'return']

    @staticmethod
    def _prepare_in_values(values: List[Any]) -> Tuple[str, List[Any]]:
        if not values:
            return "1=0", []
        placeholders = ",".join(["%s"] * len(values))
        return f"({placeholders})", [str(v).strip().replace("'", "''") if isinstance(v, str) else v for v in values]

    @staticmethod
    def _to_utc(date_str: Optional[str], time_part: str = "00:00:00") -> Optional[str]:
        if not date_str:
            return None
        try:
            format_str = "%Y-%m-%d %H:%M:%S" if " " in date_str else f"%Y-%m-%d {time_part}"
            dt = datetime.strptime(date_str if " " in date_str else f"{date_str} {time_part}", format_str)
            dt_utc = dt - timedelta(hours=3)
            return dt_utc.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Ошибка парсинга даты: {date_str} → {e}")
            return None

    @staticmethod
    def _convert_decimal_to_float(data: Any) -> Any:
        if isinstance(data, dict):
            return {k: DBService._convert_decimal_to_float(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [DBService._convert_decimal_to_float(item) for item in data]
        elif isinstance(data, Decimal):
            return float(data)
        return data

    @staticmethod
    def _execute_with_retry(query: str, params: List[Any], retries: int = 3) -> List[Dict]:
        for attempt in range(retries):
            try:
                start = time.time()
                with connections['itrade'].cursor() as cursor:
                    cursor.execute(query, params)
                    columns = [col[0] for col in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                duration = time.time() - start
                logger.info(f">>> Запрос выполнен за {duration:.2f}с, строк: {len(results)}")
                return DBService._convert_decimal_to_float(results)
            except Exception as e:
                if attempt < retries - 1 and ('Lost connection' in str(e) or 'Server has gone away' in str(e)):
                    logger.warning(f"Переподключение... попытка {attempt + 1}")
                    time.sleep(3)
                    connections['itrade'].close()
                    continue
                logger.error(f"Ошибка выполнения запроса: {e}")
                return []

    @staticmethod
    def get_kpi_plans_data(filters: Optional[Dict] = None) -> List[Dict]:
        if filters is None:
            filters = {}

        date_from = filters.get('date_from', '2024-01-01')
        date_to = filters.get('date_to', '2025-12-31')

        query = """
        SELECT
            offer_plan.id as call_eff_kpi_id,
            offer_plan.period_date as call_eff_period_date,
            offer_plan.offer_id as call_eff_offer_id,
            aff.external_id as call_eff_affiliate_id,
            LEFT(DATE_ADD(offer_plan.updated_at, INTERVAL 3 HOUR), 10) as call_eff_plan_update_date,
            offer_plan.confirmation_price as call_eff_confirmation_price,
            offer_plan.buyout_price as call_eff_buyout_price,
            offer_plan.operator_efficiency as call_eff_operator_efficiency,
            LEFT(DATE_ADD(offer_plan.operator_efficiency_updated_at, INTERVAL 3 HOUR), 10) as call_eff_operator_efficiency_update_date,
            offer_plan.planned_approve_from as call_eff_planned_approve,
            LEFT(DATE_ADD(offer_plan.planned_approve_update_at, INTERVAL 3 HOUR), 10) as call_eff_approve_update_date,
            offer_plan.planned_buyout_from as call_eff_planned_buyout,
            LEFT(DATE_ADD(offer_plan.planned_buyout_update_at, INTERVAL 3 HOUR), 10) as call_eff_buyout_update_date,
            offer_plan.confirmation_price as call_eff_confirmation_price,
            LEFT(DATE_ADD(offer_plan.confirmation_price_updated_at, INTERVAL 3 HOUR), 10) as call_eff_confirmation_price_update_date,
            offer_plan.buyout_price as call_eff_buyout_price,
            LEFT(DATE_ADD(offer_plan.buyout_price_updated_at, INTERVAL 3 HOUR), 10) as call_eff_buyout_price_update_date
        FROM partners_tlofferplanneddataperiod AS offer_plan
        LEFT JOIN partners_affiliate aff ON aff.id = offer_plan.affiliate_id
        WHERE 
            offer_plan.operator_efficiency IS NOT NULL 
            AND offer_plan.operator_efficiency > 0
            AND offer_plan.period_date >= %s
            AND offer_plan.period_date <= %s
            AND YEAR(offer_plan.period_date) >= 2024
        ORDER BY offer_plan.period_date ASC
        """
        params = [date_from, date_to]
        results = DBService._execute_with_retry(query, params)
        logger.info(f">>> KPI планы (отфильтрованные): {len(results)} записей")
        return results

    @staticmethod
    def get_offers(v: Dict) -> List[Dict]:
        offer_ids = v.get('offer_id', [])
        categories = v.get('category', [])

        query = """
        SELECT
            po.id as id,
            po.name as name,
            go.name as category_name
        FROM partners_offer po
        LEFT JOIN partners_assignedoffer ao ON ao.offer_id = po.id
        LEFT JOIN partners_groupoffer go ON ao.group_id = go.id
        WHERE go.name NOT IN ({})
        """.format(",".join(["%s"] * len(DBService.EXCLUDED_CATEGORIES)))

        params = DBService.EXCLUDED_CATEGORIES.copy()

        if categories:
            placeholders, cat_params = DBService._prepare_in_values(categories)
            query += f" AND go.name IN {placeholders}"
            params.extend(cat_params)

        if offer_ids:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND po.id IN {placeholders}"
            params.extend(offer_params)

        return DBService._execute_with_retry(query, params)

    @staticmethod
    def _build_calls_query(filters: Dict, last_id: int, limit: int) -> Tuple[str, List[Any]]:
        date_from = DBService._to_utc(filters.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(filters.get('date_to'), "23:59:59")
        if not date_from or not date_to:
            raise ValueError("Неверные даты для звонков")

        offer_ids = filters.get('offer_id', [])
        aff_ids = filters.get('aff_id', [])

        query = """
        SELECT DISTINCT
            ace.id as call_eff_id,
            ccd.id as call_eff_crm_id,
            po.id as call_eff_offer_id,
            ace.uniqueid as call_eff_uniqueid,
            ace.billsec as call_eff_billsec,
            ccd.oktell_duration as call_eff_billsec_exact,
            LEFT(DATE_ADD(ace.calldate, INTERVAL 3 HOUR), 10) AS call_eff_calldate,
            uu.id as call_eff_operator_id,
            ccd.crm_lead_id as call_eff_crm_lead_id,
            pt.webmaster_id as call_eff_affiliate_id,
            lv_op.username as lv_username,
            po.name as offer_name,
            go.name as category_name
        FROM partners_atscallevent ace
        LEFT JOIN crm_call_calldata ccd ON ccd.id = ace.assigned_call_data_id
        LEFT JOIN partners_lvlead lvl ON ace.lvlead_id = lvl.id
        LEFT JOIN partners_tllead pt ON lvl.tl_id = pt.external_id
        LEFT JOIN partners_offer po ON pt.offer_id = po.id
        LEFT JOIN partners_assignedoffer ao ON ao.offer_id = po.id
        LEFT JOIN partners_groupoffer go ON ao.group_id = go.id
        LEFT JOIN partners_lvoperator lv_op ON lv_op.id = ace.lvoperator_id
        LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = lv_op.id
        LEFT JOIN users_user uu ON uu.id = pu.user_id
        LEFT JOIN users_department ud ON ud.id = uu.department_id
        LEFT JOIN crm_call_oktelltask cco ON ace.oktell_task_id = cco.id
        WHERE ace.billsec >= 30
            AND ace.calldate >= %s
            AND ace.calldate < %s
            AND ace.id > %s
            AND (go.name IS NULL OR go.name NOT IN ({}))
            AND po.id IS NOT NULL
            AND lv_op.username IS NOT NULL
            AND ((ud.name LIKE '%%_НП_%%' OR ud.name LIKE '%%_СП_%%') OR (cco.type = 'new_sales'))
        """.format(",".join(["%s"] * len(DBService.EXCLUDED_CATEGORIES)))

        params = [date_from, date_to, last_id] + DBService.EXCLUDED_CATEGORIES

        if offer_ids:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND po.id IN {placeholders}"
            params.extend(offer_params)

        if aff_ids:
            placeholders, aff_params = DBService._prepare_in_values(aff_ids)
            query += f" AND pt.webmaster_id IN {placeholders}"
            params.extend(aff_params)

        query += " ORDER BY ace.id ASC LIMIT %s"
        params.append(limit)
        return query, params

    @staticmethod
    def get_calls_batch_exact(v: Dict, last_id: int = 0, limit: int = 200) -> List[Dict]:
        try:
            query, params = DBService._build_calls_query(v, last_id, limit)
            return DBService._execute_with_retry(query, params)
        except Exception as e:
            logger.error(f">>> Ошибка батча звонков: {e}")
            return []

    @staticmethod
    def get_calls(v: Dict) -> List[Dict]:
        all_calls = []
        last_id = 0
        batch_size = 200
        total_loaded = 0
        logger.info(">>> Начало загрузки звонков с курсорной пагинацией...")

        while True:
            batch = DBService.get_calls_batch_exact(v, last_id, batch_size)
            if not batch:
                break
            all_calls.extend(batch)
            total_loaded += len(batch)
            last_id = int(batch[-1]['call_eff_id'])

            logger.info(f">>> Звонки: загружено {total_loaded}...")

            if len(batch) < batch_size:
                break
            if total_loaded > 50_000:
                logger.warning(">>> Звонки: достигнут лимит в 50k записей")
                break

        logger.info(f">>> ИТОГО загружено звонков: {len(all_calls)}")
        return all_calls

    @staticmethod
    def _build_leads_query(filters: Dict, last_id: int, limit: int, container: bool = False) -> Tuple[str, List[Any]]:
        date_from = DBService._to_utc(filters.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(filters.get('date_to'), "23:59:59")
        if not date_from or not date_to:
            raise ValueError("Неверные даты")

        advertiser = [a.lower() for a in filters.get('advertiser', [])]
        offer_ids = filters.get('offer_id', [])
        categories = filters.get('category', [])
        lv_ops = [op.lower() for op in filters.get('lv_op', [])]
        aff_ids = filters.get('aff_id', [])

        base_field = "lv.created_at" if container else "lv.approved_at"

        select_fields = """
            DISTINCT
            crm_leads_crmlead.id as call_eff_crm_lead_id,
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
        """ if not container else """
            DISTINCT
            crm_leads_crmlead.id as lead_container_crm_lead_id,
            crm_leads_crmlead.id as call_eff_crm_lead_id,
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
            NULL as lv_username,
            group_offer.name as category_name
        """

        excluded_placeholders = ','.join(['%s'] * len(DBService.EXCLUDED_CATEGORIES))

        query = f"""
        SELECT {select_fields}
        FROM partners_lvlead lv
        LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
        LEFT JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
        LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = lv.operator_id
        LEFT JOIN users_user uu ON uu.id = pu.user_id
        LEFT JOIN partners_lvleadstatuses AS lv_status ON lv.leadvertex_status_id = lv_status.id
        LEFT JOIN partners_tllead AS tl_lead ON lv.tl_id = tl_lead.external_id
        LEFT JOIN partners_tllead AS pt ON lv.tl_id = pt.external_id
        LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
        LEFT JOIN partners_offer as offer ON pt.offer_id = offer.id
        LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
        LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
        WHERE offer.id IS NOT NULL
            AND lv_op.username IS NOT NULL
            AND group_offer.name NOT IN ({excluded_placeholders})
            AND crm_leads_crmlead.id > %s
            AND DATE_ADD({base_field}, INTERVAL 3 HOUR) >= %s
            AND DATE_ADD({base_field}, INTERVAL 3 HOUR) < %s
        """

        params = DBService.EXCLUDED_CATEGORIES + [last_id, date_from, date_to]

        if categories:
            placeholders, cat_params = DBService._prepare_in_values(categories)
            query += f" AND group_offer.name IN {placeholders}"
            params.extend(cat_params)

        if offer_ids:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND offer.id IN {placeholders}"
            params.extend(offer_params)

        if advertiser:
            placeholders, adv_params = DBService._prepare_in_values(advertiser)
            query += f" AND LOWER(subsystem.name) IN {placeholders}"
            params.extend(adv_params)

        if lv_ops and not container:
            placeholders, op_params = DBService._prepare_in_values(lv_ops)
            query += f" AND LOWER(lv_op.username) IN {placeholders}"
            params.extend(op_params)

        if aff_ids:
            placeholders, aff_params = DBService._prepare_in_values(aff_ids)
            query += f" AND pt.webmaster_id IN {placeholders}"
            params.extend(aff_params)

        query += " ORDER BY crm_leads_crmlead.id ASC LIMIT %s"
        params.append(limit)

        return query, params

    @staticmethod
    def get_leads_batch_exact(v: Dict, last_id: int = 0, limit: int = 3000) -> List[Dict]:
        try:
            query, params = DBService._build_leads_query(v, last_id, limit, container=False)
            results = DBService._execute_with_retry(query, params)

            logger.info(f">>> Лиды батч: {len(results)} (last_id: {last_id})")

            if results and len(results) > 0:
                logger.info(
                    f">>> Пример лида: offer_id={results[0].get('offer_id')}, "
                    f"approved_at={results[0].get('call_eff_approved_at')}, "
                    f"status_group={results[0].get('call_eff_status_group')}"
                )

            return results

        except Exception as e:
            logger.error(f">>> Ошибка батча лидов: {e}")
            return []

    @staticmethod
    def get_leads(v: Dict) -> List[Dict]:
        all_leads = []
        last_id = 0
        batch_size = 3000
        total_loaded = 0
        logger.info(">>> Начало загрузки лидов...")

        while True:
            batch = DBService.get_leads_batch_exact(v, last_id, batch_size)
            if not batch:
                break

            all_leads.extend(batch)
            total_loaded += len(batch)
            last_id = int(batch[-1]['call_eff_crm_lead_id'])

            logger.info(f">>> Лиды: загружено {total_loaded}...")

            if len(batch) < batch_size:
                break

        logger.info(f">>> ИТОГО загружено лидов: {len(all_leads)}")
        return all_leads

    @staticmethod
    def get_leads_container_batch_exact(v: Dict, last_id: int = 0, limit: int = 10000) -> List[Dict]:
        try:
            query, params = DBService._build_leads_query(v, last_id, limit, container=True)
            results = DBService._execute_with_retry(query, params)
            logger.info(f">>> Контейнеры батч: {len(results)} (last_id: {last_id})")
            return results
        except Exception as e:
            logger.error(f">>> Ошибка батча контейнеров: {e}")
            return []

    @staticmethod
    def get_leads_container(v: Dict) -> List[Dict]:
        all_data = []
        last_id = 0
        batch_size = 10000
        total_loaded = 0
        logger.info(">>> Начало загрузки контейнеров лидов...")

        while True:
            batch = DBService.get_leads_container_batch_exact(v, last_id, batch_size)
            if not batch:
                break

            all_data.extend(batch)
            total_loaded += len(batch)
            last_id = int(batch[-1]['lead_container_crm_lead_id'])

            logger.info(f">>> Контейнеры: загружено {total_loaded}...")

            if len(batch) < batch_size:
                break

        logger.info(f">>> ИТОГО загружено контейнеров: {len(all_data)}")
        return all_data

    @staticmethod
    def is_fake_approve(lead: Dict[str, Any]) -> str:
        """ТОЧНАЯ РЕАЛИЗАЦИЯ ИЗ ЭТАЛОНА leads_processing.txt"""
        
        status_verbose = lead.get('status_verbose')
        status_group = lead.get('status_group')
        approved_at = lead.get('approved_at')
        canceled_at = lead.get('canceled_at')

        if status_verbose is None:
            status_verbose = lead.get('call_eff_status_verbose')
        if status_group is None:
            status_group = lead.get('call_eff_status_group')
        if approved_at is None:
            approved_at = lead.get('call_eff_approved_at')
        if canceled_at is None:
            canceled_at = lead.get('call_eff_canceled_at')

        if status_verbose is None:
            return "Can't find lead.status_verbose"
        if status_group is None:
            return "Can't find lead.status_group"
        if approved_at is None:
            return "Can't find lead.approved_at"
        if canceled_at is None:
            return "Can't find lead.canceled_at"

        status_verbose_lower = str(status_verbose).lower()
        status_group_lower = str(status_group).lower()

        if status_group_lower not in [g.lower() for g in DBService.GOOD_APPROVE_STATUS_GROUP]:
            return f"Группа статусов: {status_group}"

        if 'отправить позже' in status_verbose_lower:
            return "Заказ в статусе 'Отправить позже'"

        if approved_at and canceled_at:
            try:
                if isinstance(approved_at, str) and isinstance(canceled_at, str):
                    if approved_at <= canceled_at and canceled_at.strip():
                        return f"Заказ отменён ({canceled_at}) после подтверждения ({approved_at})"
            except Exception:
                pass

        if not approved_at or approved_at.strip() == '':
            return "Отсутствует дата подтверждения"

        for bad_status in DBService.BAD_APPROVE_STATUS:
            if bad_status in status_verbose_lower:
                return f"Заказ в статусе: {status_verbose}"

        return ""

    @staticmethod
    def is_fake_buyout(lead: Dict[str, Any]) -> str:
        status_group = lead.get('status_group')
        buyout_at = lead.get('buyout_at')

        if status_group is None:
            return "Can't find lead.status_group"
        if buyout_at is None:
            return "Can't find lead.buyout_at"

        if str(status_group).lower() != 'paid':
            return "Лид не в группе статусов paid"
        if not buyout_at or buyout_at.strip() == '':
            return "Отсутствует дата выкупа"

        return ""

    @staticmethod
    def is_processing(lead: Dict[str, Any]) -> str:
        status_group = lead.get('status_group')
        if status_group is None:
            return "Can't find lead.status_group"

        if str(status_group).lower() == 'processing':
            return ""
        return "Лид не в группе статусов processing"

    @staticmethod
    def get_leads_processed(v: Dict) -> List[Dict]:
        leads = DBService.get_leads(v)
        logger.info(f">>> СЫРЫЕ лиды из БД: {len(leads)} записей")

        if leads:
            for i in range(min(3, len(leads))):
                lead = leads[i]
                logger.info(
                    f">>> Пример лида {i}: offer_id={lead.get('offer_id')}, "
                    f"approved_at={lead.get('call_eff_approved_at')}, "
                    f"status_group={lead.get('call_eff_status_group')}, "
                    f"status_verbose={lead.get('call_eff_status_verbose')}"
                )

        processed = []
        valid_count = 0
        fake_count = 0

        for lead in leads:
            fake_reason = DBService.is_fake_approve(lead)

            if not fake_reason:
                lead['is_fake_approve'] = False
                lead['fake_reason'] = ""
                lead['is_processing'] = DBService.is_processing(lead) == ""
                lead['is_fake_buyout'] = DBService.is_fake_buyout(lead) != ""
                valid_count += 1
            else:
                lead['is_fake_approve'] = True
                lead['fake_reason'] = fake_reason
                lead['is_processing'] = False
                lead['is_fake_buyout'] = True
                fake_count += 1

            processed.append(lead)

        logger.info(f">>> Обработано лидов: {len(processed)} (валидных: {valid_count}, фейков: {fake_count})")
        return processed

    @staticmethod
    def get_leads_container_processed(v: Dict) -> List[Dict]:
        containers = DBService.get_leads_container(v)
        processed = []

        for lead in containers:
            lead['fake_container_reason'] = DBService.is_fake_approve(lead)
            lead['is_fake_approve'] = DBService.is_fake_approve(lead) != ""
            lead['is_processing'] = DBService.is_processing(lead) == ""

            processed.append(lead)

        logger.info(f">>> Обработано контейнеров: {len(processed)}")
        return processed