# numu/management/commands/import_discs.py
#
# Management command to import all 4 disc JSON files into the database.
#
# Usage:
#   python manage.py import_discs                        # import all 4 discs
#   python manage.py import_discs --disc 1               # import one disc only
#   python manage.py import_discs --dry-run              # validate, no DB writes
#   python manage.py import_discs --disc 2 --dry-run
#
# The command is idempotent by design:
#   - Lexemes: get_or_create on paiute_normalized
#   - Lessons: skips if lesson_number already exists (re-run safe)
#   - Entries and all grammar rows: skips if lesson already imported
#
# source_notes from any entry are automatically written to review_flags.

import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from numu.models import (
    Disc, Lesson, AudioFile, Lexeme, Entry,
    VerbParadigmForm, VerbPhraseForm,
    ColorForm, ColorExampleSentence, ColorApplicationEntry,
    SuffixExample, SentenceEntry, PrayerLine,
    NumberEntry, AnimalCategory, ReviewFlag,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_or_create_lexeme(paiute_text):
    """
    Canonical lexeme lookup/creation.
    Always match on lowercase normalized form.
    Sets needs_lexeme_review=True on auto-created lexemes.
    Sets is_multi_sense=True if the same normalized form maps to
    a different surface spelling (cross-disc homophone).
    """
    normalized = paiute_text.lower()
    lexeme, created = Lexeme.objects.get_or_create(
        paiute_normalized=normalized,
        defaults={
            'paiute': paiute_text,
            'needs_lexeme_review': True,
        }
    )
    if not created and lexeme.paiute != paiute_text:
        # Same normalized form, different surface spelling → multi-sense or variant
        lexeme.is_multi_sense = True
        lexeme.needs_lexeme_review = True
        lexeme.save(update_fields=['is_multi_sense', 'needs_lexeme_review'])
    return lexeme, created


def create_flag(obj, note, source='transcription'):
    """Create a ReviewFlag pointing at any model instance."""
    ct = ContentType.objects.get_for_model(obj)
    ReviewFlag.objects.create(
        content_type=ct,
        object_id=obj.id,
        flag_note=note,
        source=source,
    )


# ── Importers per lesson type ─────────────────────────────────────────────────

def import_standard_entries(lesson_obj, entries_data, dry_run, stats):
    """Standard vocab entries → entries table. Also handles eating_related_states."""
    for i, e in enumerate(entries_data):
        paiute = e.get('paiute', '').strip()
        english = e.get('english', '').strip()
        if not paiute or not english:
            continue
        if dry_run:
            stats['entries'] += 1
            continue
        lexeme, _ = get_or_create_lexeme(paiute)
        stats['lexemes'] += (1 if _ else 0)
        entry = Entry.objects.create(
            lesson=lesson_obj,
            lexeme=lexeme,
            paiute=paiute,
            pronunciation=e.get('pronunciation', '') or None,
            english=english,
            context_note=e.get('context_note', '') or None,
            source_notes=e.get('notes', '') or None,
            sort_order=e.get('item_number', i + 1),
        )
        stats['entries'] += 1
        if entry.source_notes:
            create_flag(entry, entry.source_notes)
            stats['flags'] += 1


def import_verb_paradigm(lesson_obj, verb_forms, phrase_forms, dry_run, stats):
    """verb_forms → verb_paradigm_forms; phrase_forms → verb_phrase_forms."""
    for i, vf in enumerate(verb_forms or []):
        if dry_run:
            stats['verb_paradigm_forms'] += 1
            continue
        form = VerbParadigmForm.objects.create(
            lesson=lesson_obj,
            paiute=vf.get('paiute', '').strip(),
            pronunciation=vf.get('pronunciation') or None,
            english=vf.get('english', '').strip(),
            grammatical_tags=None,   # assigned manually post-import
            sort_order=i + 1,
            source_notes=vf.get('notes') or None,
        )
        stats['verb_paradigm_forms'] += 1
        if form.source_notes:
            create_flag(form, form.source_notes)
            stats['flags'] += 1

    for i, pf in enumerate(phrase_forms or []):
        if dry_run:
            stats['verb_phrase_forms'] += 1
            continue
        VerbPhraseForm.objects.create(
            lesson=lesson_obj,
            paiute=pf.get('paiute', '').strip(),
            english=pf.get('english', '').strip(),
            sort_order=i + 1,
            source_notes=pf.get('notes') or None,
        )
        stats['verb_phrase_forms'] += 1


def import_color_entries(lesson_obj, color_entries, dry_run, stats):
    """color_entries → color_forms + color_example_sentences."""
    for i, ce in enumerate(color_entries or []):
        if dry_run:
            stats['color_forms'] += 1
            continue
        cf = ColorForm.objects.create(
            lesson=lesson_obj,
            english=ce.get('english', '').strip(),
            adjective=ce.get('adjective', '').strip(),
            predicate=ce.get('predicate', '').strip(),
            predicate_gloss=ce.get('predicate_gloss', '').strip(),
            noun_form=ce.get('noun_form', '').strip(),
            noun_gloss=ce.get('noun_gloss', '').strip(),
            extra_forms=ce.get('extra_forms') or None,
            compound_components=ce.get('compound_components') or None,
            compound_result=ce.get('compound_result') or None,
            compound_english=ce.get('compound_english') or None,
            sort_order=i + 1,
            source_notes=ce.get('notes') or None,
        )
        stats['color_forms'] += 1
        if cf.source_notes:
            create_flag(cf, cf.source_notes)
            stats['flags'] += 1
        for j, ex in enumerate(ce.get('examples', []) or []):
            ColorExampleSentence.objects.create(
                color_form=cf,
                paiute=ex.get('paiute', '').strip(),
                english=ex.get('english', '').strip(),
                sort_order=j + 1,
            )


def import_color_application_entries(lesson_obj, entries, dry_run, stats):
    for i, e in enumerate(entries or []):
        if dry_run:
            stats['color_application_entries'] += 1
            continue
        obj = ColorApplicationEntry.objects.create(
            lesson=lesson_obj,
            source_number=e.get('item_number', i + 1),
            paiute=e.get('paiute', '').strip(),
            english=e.get('english', '').strip(),
            source_notes=e.get('notes') or None,
        )
        stats['color_application_entries'] += 1
        if obj.source_notes:
            create_flag(obj, obj.source_notes)
            stats['flags'] += 1


def import_suffix_entries(lesson_obj, suffix_entries, dry_run, stats):
    """Disc 4 suffix lessons: suffix_entries → suffix_examples."""
    suffix = lesson_obj.notes and lesson_obj.notes.split()[0] or ''
    for i, se in enumerate(suffix_entries or []):
        if dry_run:
            stats['suffix_examples'] += 1
            continue
        base_paiute = se.get('base_verb', '').strip()
        lexeme = None
        if base_paiute:
            lexeme, created = get_or_create_lexeme(base_paiute)
            if created:
                stats['lexemes'] += 1
        obj = SuffixExample.objects.create(
            lesson=lesson_obj,
            suffix=se.get('suffix', suffix).strip(),
            base_verb=base_paiute,
            base_verb_english=se.get('base_verb_english') or None,
            base_verb_lexeme=lexeme,
            suffixed_form=se.get('suffixed_form', '').strip(),
            english=se.get('english', '').strip(),
            sort_order=i + 1,
            source_notes=se.get('notes') or None,
        )
        stats['suffix_examples'] += 1
        if obj.source_notes:
            create_flag(obj, obj.source_notes)
            stats['flags'] += 1


def import_sentence_entries(lesson_obj, sentence_entries, dry_run, stats):
    for i, se in enumerate(sentence_entries or []):
        if dry_run:
            stats['sentence_entries'] += 1
            continue
        obj = SentenceEntry.objects.create(
            lesson=lesson_obj,
            paiute=se.get('paiute', '').strip(),
            english=se.get('english', '').strip(),
            components=se.get('word_glosses') or se.get('components') or None,
            sort_order=i + 1,
            source_notes=se.get('notes') or None,
        )
        stats['sentence_entries'] += 1
        if obj.source_notes:
            create_flag(obj, obj.source_notes)
            stats['flags'] += 1


def import_prayer_lines(lesson_obj, prayer_lines, dry_run, stats):
    for line in prayer_lines or []:
        if dry_run:
            stats['prayer_lines'] += 1
            continue
        PrayerLine.objects.create(
            lesson=lesson_obj,
            line_number=line.get('line_number', 0),
            paiute=line.get('paiute', '').strip(),
            english=line.get('english', '').strip(),
            is_ritual_action=line.get('is_ritual_action', False),
            ritual_note=line.get('ritual_note') or None,
        )
        stats['prayer_lines'] += 1


def import_number_entries(lesson_obj, base_numbers, compound_numbers, dry_run, stats):
    for n in base_numbers or []:
        if dry_run:
            stats['number_entries'] += 1
            continue
        NumberEntry.objects.create(
            lesson=lesson_obj,
            paiute=n.get('paiute', '').strip(),
            english=n.get('english', '').strip(),
            numeral=n.get('value') or None,
            entry_type='base',
            components=None,
            sort_order=n.get('value') or None,
            source_notes=n.get('notes') or None,
        )
        stats['number_entries'] += 1
    for n in compound_numbers or []:
        if dry_run:
            stats['number_entries'] += 1
            continue
        obj = NumberEntry.objects.create(
            lesson=lesson_obj,
            paiute=n.get('paiute', '').strip(),
            english=n.get('english', '').strip(),
            numeral=n.get('value') or None,
            entry_type='compound',
            components=n.get('components') or None,
            sort_order=n.get('value') or None,
            source_notes=n.get('notes') or None,
        )
        stats['number_entries'] += 1
        if obj.source_notes:
            create_flag(obj, obj.source_notes)
            stats['flags'] += 1


def import_animal_categories(lesson_obj, categories, dry_run, stats):
    for i, cat in enumerate(categories or []):
        if dry_run:
            stats['animal_categories'] += 1
            continue
        AnimalCategory.objects.create(
            lesson=lesson_obj,
            paiute=cat.get('paiute', '').strip(),
            english=cat.get('english', '').strip(),
            sort_order=i + 1,
        )
        stats['animal_categories'] += 1


# ── Lesson dispatcher ─────────────────────────────────────────────────────────

def import_lesson(lesson_data, disc_obj, dry_run, stats):
    """
    Detect lesson type from JSON keys and route to the correct importer.
    Creates the Lesson and AudioFile rows first, then dispatches.
    """
    lesson_number = lesson_data['lesson_number']

    # Skip if already imported
    if Lesson.objects.filter(lesson_number=lesson_number).exists():
        stats['skipped'] += 1
        return

    lesson_obj = None
    if not dry_run:
        lesson_obj = Lesson.objects.create(
            disc=disc_obj,
            lesson_number=lesson_number,
            title=lesson_data.get('title', '').strip(),
            category=lesson_data.get('category', '').strip(),
            page=lesson_data.get('page', '').strip(),
            section_title=lesson_data.get('section_title') or None,
            notes=lesson_data.get('color_morphology_note')
                  or lesson_data.get('grammar_suffix_note')
                  or None,
        )
        audio_filename = lesson_data.get('audio_file')
        if audio_filename:
            AudioFile.objects.create(lesson=lesson_obj, filename=audio_filename)
    stats['lessons'] += 1

    if dry_run:
        # Just count entries without creating anything
        lesson_obj = type('FakeLesson', (), {'id': None, 'notes': None})()

    # Route by JSON key presence
    if lesson_data.get('verb_forms') is not None:
        import_verb_paradigm(
            lesson_obj,
            lesson_data.get('verb_forms', []),
            lesson_data.get('phrase_forms', []),
            dry_run, stats
        )
        # Some verb paradigm lessons also have eating_related_states (L28)
        if lesson_data.get('eating_related_states'):
            import_standard_entries(lesson_obj, lesson_data['eating_related_states'], dry_run, stats)

    elif lesson_data.get('color_entries') is not None:
        import_color_entries(lesson_obj, lesson_data['color_entries'], dry_run, stats)

    elif lesson_data.get('color_application_entries') is not None:
        import_color_application_entries(lesson_obj, lesson_data['color_application_entries'], dry_run, stats)

    elif lesson_data.get('suffix_entries') is not None:
        import_suffix_entries(lesson_obj, lesson_data['suffix_entries'], dry_run, stats)

    elif lesson_data.get('sentence_entries') is not None:
        import_sentence_entries(lesson_obj, lesson_data['sentence_entries'], dry_run, stats)
        # Paiute W's lessons may also have standard entries
        if lesson_data.get('entries'):
            import_standard_entries(lesson_obj, lesson_data['entries'], dry_run, stats)

    elif lesson_data.get('prayer_lines') is not None:
        import_prayer_lines(lesson_obj, lesson_data['prayer_lines'], dry_run, stats)

    elif lesson_data.get('base_numbers') is not None or lesson_data.get('compound_numbers') is not None:
        import_number_entries(
            lesson_obj,
            lesson_data.get('base_numbers', []),
            lesson_data.get('compound_numbers', []),
            dry_run, stats
        )

    elif lesson_data.get('animal_categories') is not None:
        import_animal_categories(lesson_obj, lesson_data['animal_categories'], dry_run, stats)
        # Animals continued may also have standard entries
        if lesson_data.get('entries'):
            import_standard_entries(lesson_obj, lesson_data['entries'], dry_run, stats)

    elif lesson_data.get('entries') is not None:
        import_standard_entries(lesson_obj, lesson_data['entries'], dry_run, stats)

    else:
        # Unknown structure — flag it
        print(f"  WARNING: L{lesson_number} has unrecognized structure. Keys: {list(lesson_data.keys())}")


# ── Management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Import Numu lesson data from disc JSON files into the database.'

    # Default path — adjust if your JSON files live elsewhere
    JSON_DIR = os.path.expanduser('~/Downloads')
    DISC_FILES = {
        1: 'numu_disc1.json',
        2: 'numu_disc2.json',
        3: 'numu_disc3.json',
        4: 'numu_disc4.json',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--disc', type=int, choices=[1, 2, 3, 4],
            help='Import a single disc only (1–4). Omit to import all.'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Validate and count without writing to the database.'
        )
        parser.add_argument(
            '--json-dir', type=str,
            help=f'Directory containing disc JSON files. Default: {self.JSON_DIR}'

        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        json_dir = options.get('json_dir') or self.JSON_DIR
        disc_filter = options.get('disc')

        discs_to_import = [disc_filter] if disc_filter else [1, 2, 3, 4]

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database writes'))

        total_stats = {
            'lessons': 0, 'skipped': 0, 'entries': 0, 'lexemes': 0,
            'verb_paradigm_forms': 0, 'verb_phrase_forms': 0,
            'color_forms': 0, 'color_application_entries': 0,
            'suffix_examples': 0, 'sentence_entries': 0,
            'prayer_lines': 0, 'number_entries': 0, 'animal_categories': 0,
            'flags': 0,
        }

        for disc_num in discs_to_import:
            filename = os.path.join(json_dir, self.DISC_FILES[disc_num])
            if not os.path.exists(filename):
                raise CommandError(f'File not found: {filename}')

            self.stdout.write(f'\nImporting Disc {disc_num}: {filename}')

            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            disc_obj = Disc.objects.get(id=disc_num)
            disc_stats = dict(total_stats)  # per-disc copy

            try:
                with transaction.atomic():
                    for lesson_data in data.get('lessons', []):
                        import_lesson(lesson_data, disc_obj, dry_run, disc_stats)
                    if dry_run:
                        raise RuntimeError('dry-run rollback')
            except RuntimeError as e:
                if 'dry-run' in str(e):
                    pass  # expected rollback
                else:
                    raise

            # Accumulate into totals
            for k in total_stats:
                total_stats[k] += disc_stats[k]

            self.stdout.write(
                f'  Disc {disc_num}: {disc_stats["lessons"]} lessons, '
                f'{disc_stats["entries"]} entries, '
                f'{disc_stats["lexemes"]} new lexemes, '
                f'{disc_stats["flags"]} flags'
            )

        self.stdout.write('\n' + self.style.SUCCESS('=== Import Summary ==='))
        for key, val in total_stats.items():
            if val:
                self.stdout.write(f'  {key:<30} {val}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN complete — no data written'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport complete'))
