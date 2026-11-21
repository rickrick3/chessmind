from django.apps import AppConfig


class GamificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gamification"

    def ready(self):
        from accounts.signals import merge_learners

        from .services import on_merge

        merge_learners.connect(on_merge, dispatch_uid="gamification-merge")
