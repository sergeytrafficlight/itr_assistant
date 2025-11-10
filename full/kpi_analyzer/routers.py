class ITradeRouter:
    """
    ВСЁ приложение kpi_analyzer — работает с default (kpi_db)
    База itrade — ТОЛЬКО для ручного чтения через .using('itrade')
    НИКАКИХ автоматических запросов в itrade!
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'kpi_analyzer':
            return 'default'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'kpi_analyzer':
            return 'default'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Разрешаем связи между объектами
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """

        """
        if app_label == 'kpi_analyzer':
            return db == 'default'


        if app_label in ['admin', 'auth', 'contenttypes', 'sessions']:
            return db == 'default'

        return None