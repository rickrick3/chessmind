from django.apps import AppConfig


class SkillsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skills"

    def ready(self):
        from accounts.signals import merge_learners

        from .services import on_merge

        # Connected after learning, gamification and puzzles (INSTALLED_APPS order): it needs their rows moved.
        merge_learners.connect(on_merge, dispatch_uid="skills-merge")
