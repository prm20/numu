from django.contrib import admin
from django.apps import apps
from .models import Course, Lesson, Entry


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = ('id', 'title', 'source', 'sort_order')
    list_editable = ('sort_order',)
    ordering      = ('sort_order', 'id')


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display       = ('lesson_number', 'title', 'course', 'category')
    list_filter        = ('course',)
    list_display_links = ('title',)
    search_fields      = ('title', 'category')


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display  = ('paiute', 'english', 'content_type', 'lesson', 'course')
    list_filter   = ('content_type', 'lesson__course')
    search_fields = ('paiute', 'english')

    def course(self, obj):
        return obj.lesson.course
    course.admin_order_field = 'lesson__course'
    course.short_description = 'Course'


# Auto-register any remaining models not already registered above
app_config = apps.get_app_config('numu')

for model in app_config.get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass