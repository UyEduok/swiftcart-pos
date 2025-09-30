from django.apps import AppConfig


class PriceSlashConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'price_slash'

    def ready(self):
        import price_slash.signals
