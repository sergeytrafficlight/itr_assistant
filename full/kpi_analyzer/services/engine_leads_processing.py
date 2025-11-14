class EngineLeadsProcessing:
    bad_approve_status = ['отправить позже', 'отмен', 'предоплаты', '4+ дней', '4 день', '3 день', '2 день', '1 день',
                          'перезвон']
    good_approve_status_group = ['accepted', 'shipped', 'paid', 'return']

    @staticmethod
    def is_fake_approve(lead):
        for field in ['status_verbose', 'status_group', 'approved_at', 'canceled_at']:
            if field not in lead:
                raise Exception(f"Can't find lead.{field}")

        if lead['status_group'] not in EngineLeadsProcessing.good_approve_status_group:
            return "Группа статусов: " + str(lead['status_group'])

        status_verbose = str(lead['status_verbose']).lower()

        if 'отправить позже' in status_verbose:
            return "Заказ в статусе 'Отправить позже'"

        approved_at = lead['approved_at']
        canceled_at = lead['canceled_at']

        # Упрощенная и корректная логика проверки дат
        if approved_at and canceled_at and approved_at <= canceled_at:
            return f"Заказ отменён ({canceled_at}) после подтверждения ({approved_at})"

        if not approved_at:
            return "Отсутствует дата подтверждения"

        for bad in EngineLeadsProcessing.bad_approve_status:
            if bad in status_verbose:
                return "Заказ в статусе: " + lead['status_verbose']

        return ""

    @staticmethod
    def is_fake_buyout(lead):
        for field in ['status_group', 'buyout_at']:
            if field not in lead:
                raise Exception(f"Can't find lead.{field}")
        if lead['status_group'] != 'paid':
            return "Лид не в группе статусов paid"
        if not lead['buyout_at']:
            return "Отсутствует дата выкупа"
        return ""

    @staticmethod
    def is_processing(lead):
        if 'status_group' not in lead:
            raise Exception("Can't find lead.status_group")
        return "" if lead['status_group'] == 'processing' else "Лид не в группе статусов processing"


engine_leads_processing = EngineLeadsProcessing()