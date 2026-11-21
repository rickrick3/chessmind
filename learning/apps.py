from django.apps import AppConfig


class LearningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "learning"

    def ready(self):
        from accounts.signals import merge_learners

        from .services import on_merge

        merge_learners.connect(on_merge, dispatch_uid="learning-merge")
