from django.contrib import admin
from django.apps import apps
from .models import Lesson, Entry   # add Entry import

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("lesson_number", "title", "disc")
    list_filter = ("disc",)
    list_display_links = ("title",)

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("paiute", "english", "lesson", "disc")
    list_filter = ("lesson__disc",)
    search_fields = ("paiute", "english")

    def disc(self, obj):
        return obj.lesson.disc
    disc.admin_order_field = "lesson__disc"
    disc.short_description = "Disc"

# keep your auto‑register loop below this
app_config = apps.get_app_config("numu")

for model in app_config.get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
