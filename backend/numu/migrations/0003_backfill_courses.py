# numu/migrations/0003_backfill_courses.py
#
# Data migration:
#   1. Create one Course row per existing Disc row (preserving all metadata)
#   2. Backfill lesson.course_id from lesson.disc_id
#
# After this migration every lesson has a valid course FK.
# The disc FK on Lesson remains as a nullable column until a future migration
# confirms data integrity and drops it.
#
# Specialized grammar tables (verb_paradigm_forms, color_forms, etc.) are NOT
# migrated into entries here — that is a separate, larger data migration that
# will be tackled after the app has been updated to write new content directly
# to entries. Existing specialized table data remains readable via the ORM
# during the transition period.

from django.db import migrations


def seed_courses_from_discs(apps, schema_editor):
    Disc   = apps.get_model('numu', 'Disc')
    Course = apps.get_model('numu', 'Course')
    Lesson = apps.get_model('numu', 'Lesson')

    disc_to_course = {}

    for disc in Disc.objects.order_by('id'):
        course = Course.objects.create(
            title          = disc.title,
            description    = None,
            dialect        = disc.dialect,
            writing_system = disc.writing_system,
            source         = 'Ralph Burns',
            total_pages    = disc.total_pages,
            notes          = disc.notes,
            sort_order     = disc.id,   # disc 1 → sort_order 1, etc.
        )
        disc_to_course[disc.id] = course.id

    # Backfill lesson.course_id from lesson.disc_id
    for lesson in Lesson.objects.select_related('disc').all():
        if lesson.disc_id is not None:
            lesson.course_id = disc_to_course[lesson.disc_id]
            lesson.save(update_fields=['course_id'])


def reverse_seed_courses(apps, schema_editor):
    Course = apps.get_model('numu', 'Course')
    Lesson = apps.get_model('numu', 'Lesson')
    # Clear course FKs on lessons before deleting courses
    Lesson.objects.all().update(course=None)
    Course.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('numu', '0002_course_entry_content_type'),
    ]

    operations = [
        migrations.RunPython(
            seed_courses_from_discs,
            reverse_code=reverse_seed_courses,
        ),
    ]