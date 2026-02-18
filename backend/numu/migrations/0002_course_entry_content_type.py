# numu/migrations/0002_course_entry_content_type.py
#
# Schema migration:
#   1. Create courses table
#   2. Add content_type, metadata, embedding columns to entries
#   3. Add course FK to lessons (nullable during migration)
#
# Follow-up data migration (0003) will:
#   - Populate Course rows from existing Disc rows
#   - Backfill lesson.course_id from lesson.disc_id
#   - Migrate specialized table data into entries with correct content_type + metadata

from django.db import migrations, models
import django.db.models.deletion
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('numu', '0001_initial'),
    ]

    operations = [

        # ── 1. Create courses table ───────────────────────────────────────────
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id',            models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title',         models.CharField(max_length=255)),
                ('description',   models.TextField(blank=True, null=True)),
                ('dialect',       models.CharField(blank=True, max_length=100, null=True)),
                ('writing_system',models.CharField(blank=True, max_length=100, null=True)),
                ('source',        models.CharField(blank=True, max_length=255, null=True)),
                ('total_pages',   models.SmallIntegerField(blank=True, null=True)),
                ('notes',         models.TextField(blank=True, null=True)),
                ('sort_order',    models.SmallIntegerField(blank=True, null=True)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'courses',
                'ordering': ['sort_order', 'id'],
            },
        ),

        # ── 2. Add course FK to lessons (nullable — backfilled in 0003) ───────
        migrations.AddField(
            model_name='lesson',
            name='course',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lessons',
                to='numu.course',
                help_text='Curriculum-agnostic replacement for disc FK.',
            ),
        ),

        # ── 3. Add content_type to entries ────────────────────────────────────
        migrations.AddField(
            model_name='entry',
            name='content_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('vocabulary',      'Vocabulary'),
                    ('verb_form',       'Verb Form'),
                    ('verb_phrase',     'Verb Phrase'),
                    ('color_form',      'Color Form'),
                    ('color_usage',     'Color Usage'),
                    ('suffix_example',  'Suffix Example'),
                    ('sentence',        'Sentence'),
                    ('prayer_line',     'Prayer Line'),
                    ('number',          'Number'),
                    ('animal_category', 'Animal Category'),
                ],
                default='vocabulary',
            ),
        ),

        # ── 4. Add metadata JSONB to entries ──────────────────────────────────
        migrations.AddField(
            model_name='entry',
            name='metadata',
            field=models.JSONField(blank=True, null=True),
        ),

        # ── 5. Add embedding vector to entries ────────────────────────────────
        migrations.AddField(
            model_name='entry',
            name='embedding',
            field=pgvector.django.VectorField(blank=True, dimensions=1536, null=True),
        ),

        # ── 6. Make entry.lexeme nullable (non-vocab entries may not have one) ─
        migrations.AlterField(
            model_name='entry',
            name='lexeme',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='entries',
                to='numu.lexeme',
            ),
        ),

        # ── 7. Add indexes on entries.content_type ────────────────────────────
        migrations.AddIndex(
            model_name='entry',
            index=models.Index(fields=['content_type'], name='entries_content_type_idx'),
        ),
        migrations.AddIndex(
            model_name='entry',
            index=models.Index(fields=['lesson', 'content_type'], name='entries_lesson_ct_idx'),
        ),
    ]