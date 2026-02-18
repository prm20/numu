# numu/models.py
#
# Django ORM models for the Numu Yadooape Language Preservation App.
# Mirrors numu_schema.sql exactly — 19 content tables.
#
# Dependencies:
#   pip install django pgvector psycopg2-binary
#
# Required in settings.py:
#   INSTALLED_APPS: add 'pgvector.django' and 'django.contrib.contenttypes'
#   DATABASES ENGINE: 'django.db.backends.postgresql'

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from pgvector.django import VectorField


# =============================================================================
# ENUMS (TextChoices)
# =============================================================================

class ContentTier(models.TextChoices):
    PUBLIC        = 'public',        'Public'
    TRIBAL_MEMBER = 'tribal_member', 'Tribal Member'
    EDUCATOR      = 'educator',      'Educator'
    ADMIN         = 'admin',         'Admin'


class UserRole(models.TextChoices):
    PUBLIC        = 'public',        'Public'
    TRIBAL_MEMBER = 'tribal_member', 'Tribal Member'
    EDUCATOR      = 'educator',      'Educator'
    ADMIN         = 'admin',         'Admin'


class FlagSource(models.TextChoices):
    TRANSCRIPTION = 'transcription', 'Transcription'
    AUDIO         = 'audio',         'Audio'
    IMPORT        = 'import',        'Import'
    MANUAL        = 'manual',        'Manual'


# =============================================================================
# CORE STRUCTURE: courses -> lessons -> audio_files
# =============================================================================

class Disc(models.Model):
    """
    One physical lesson disc (1-4). id is the disc number, not auto-incremented.
    DEPRECATED: retained for data migration only. Use Course going forward.
    All lesson data has been migrated to Course. Do not add new lessons here.
    """
    id             = models.SmallIntegerField(primary_key=True)
    title          = models.TextField()
    dialect        = models.TextField(default='Pyramid Lake Paiute Tribe')
    writing_system = models.TextField(default='Wycliffe')
    total_pages    = models.SmallIntegerField()
    notes          = models.TextField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discs'

    def __str__(self):
        return self.title


class Course(models.Model):
    """
    Top-level grouping of lessons. Curriculum-agnostic replacement for Disc.

    Ralph Burns' four discs are represented as four Course rows.
    Future curricula (WCSD Paiute classes, community recordings, etc.)
    are each their own Course — no schema changes required.

    source: who authored the curriculum, e.g. "Ralph Burns" or "WCSD / Stacey Burns"
    sort_order: controls display ordering in the app
    """
    title          = models.CharField(max_length=255)
    description    = models.TextField(blank=True, null=True)
    dialect        = models.CharField(max_length=100, blank=True, null=True)
    writing_system = models.CharField(max_length=100, blank=True, null=True)
    source         = models.CharField(max_length=255, blank=True, null=True)
    total_pages    = models.SmallIntegerField(null=True, blank=True)
    notes          = models.TextField(blank=True, null=True)
    sort_order     = models.SmallIntegerField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'courses'
        ordering  = ['sort_order', 'id']

    def __str__(self):
        return self.title


class Lesson(models.Model):
    """
    One lesson within a course.
    lesson_number is sequential across ALL courses in the Ralph Burns curriculum (4-44).
    Future curricula may use their own numbering — lesson_number is unique per course,
    not globally unique once multiple courses exist.

    page: "disc.page" format from source, e.g. "2.5" (Ralph Burns specific, nullable)
    section_title: optional section header from source, e.g. "Numudooe"
    notes: top-level structural notes spanning multiple entries
    content_tier defaults to 'tribal_member' -- lessons are restricted by default.
    """
    course        = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='lessons')
    # Keep disc FK temporarily during migration — will be removed in a follow-up migration
    disc          = models.ForeignKey(
        Disc, on_delete=models.PROTECT, related_name='lessons',
        null=True, blank=True,
        help_text='Deprecated: use course instead.'
    )
    lesson_number = models.SmallIntegerField(unique=True)
    title         = models.TextField()
    category      = models.TextField()
    page          = models.TextField()
    section_title = models.TextField(blank=True, null=True)
    content_tier  = models.CharField(
        max_length=20, choices=ContentTier.choices, default=ContentTier.TRIBAL_MEMBER
    )
    notes         = models.TextField(blank=True, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lessons'
        ordering = ['lesson_number']

    def __str__(self):
        return f'L{self.lesson_number}: {self.title}'


class AudioFile(models.Model):
    """
    Audio file associated with a lesson (currently 1:1 with lessons).
    entry_id nullable -- reserved for future per-entry audio clips.
    Constraint: at least one of lesson or entry must be non-null.
    """
    filename         = models.TextField()
    s3_key           = models.TextField(blank=True, null=True)
    duration_seconds = models.SmallIntegerField(null=True, blank=True)
    lesson           = models.ForeignKey(
        Lesson, on_delete=models.PROTECT, null=True, blank=True, related_name='audio_files'
    )
    entry            = models.ForeignKey(
        'Entry', on_delete=models.SET_NULL, null=True, blank=True, related_name='audio_files'
    )
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audio_files'
        constraints = [
            models.CheckConstraint(
                check=models.Q(lesson__isnull=False) | models.Q(entry__isnull=False),
                name='audio_has_parent'
            )
        ]

    def __str__(self):
        return self.filename


# =============================================================================
# LEXEME LAYER
# =============================================================================

class Lexeme(models.Model):
    """
    Canonical Paiute word form. Multiple entries can share one lexeme.

    paiute_normalized is lowercase-only -- used exclusively for dedup matching.
    NEVER use it for display; always use paiute (Wycliffe capitalization).

    Import: Lexeme.objects.get_or_create(paiute_normalized=paiute.lower())
    Auto-linked lexemes get needs_lexeme_review=True for post-import audit.
    is_multi_sense flags known cross-disc homophones:
        Taba (antelope squirrel / sun), Numu (people / liver),
        Tookoo (body/skin/flesh / meat), Wogope (pine tree / forest), etc.
    """
    paiute              = models.TextField()
    paiute_normalized   = models.TextField(unique=True)
    is_multi_sense      = models.BooleanField(default=False)
    needs_lexeme_review = models.BooleanField(default=False)
    embedding           = VectorField(dimensions=1536, null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lexemes'

    def save(self, *args, **kwargs):
        if self.paiute:
            self.paiute_normalized = self.paiute.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.paiute


# =============================================================================
# BASE ENTRIES
# =============================================================================

class Entry(models.Model):
    """
    Universal content entry. Curriculum-agnostic — covers all content types
    from any curriculum source via content_type + metadata JSONB.

    content_type identifies the kind of content. The base set covers Ralph Burns'
    curriculum; new values can be added for future curricula without schema changes.

    metadata JSONB holds structured data specific to each content_type:

        'vocabulary'      — no metadata required (paiute/english/pronunciation sufficient)

        'verb_form'       — {"grammatical_tags": {"aspect": "past", "number": "singular"},
                              "base_verb_lexeme_id": 42}

        'verb_phrase'     — no extra metadata typically needed

        'color_form'      — {"adjective": "Atsakweta", "predicate": "Atsakweta'a",
                              "predicate_gloss": "is red", "noun_form": "Atsakwetadu",
                              "noun_gloss": "red one", "extra_forms": [...],
                              "compound_components": "Atsa + Kwasu",
                              "compound_result": "Atsakwasu",
                              "compound_english": "red shirt",
                              "examples": [{"paiute": "...", "english": "..."}]}

        'color_usage'     — {"source_number": 3}

        'suffix_example'  — {"suffix": "-kwu", "base_verb": "Nadakwunae",
                              "base_verb_english": "jump", "base_verb_lexeme_id": 17,
                              "suffixed_form": "Nadakwunaekwu"}

        'sentence'        — {"components": {"what": "Hemma", "you": "U", "see": "Poone"}}

        'prayer_line'     — {"line_number": 3, "is_ritual_action": false,
                              "ritual_note": null}

        'number'          — {"numeral": 11, "entry_type": "compound",
                              "components": "Naemisa + Sumu'yoo"}

        'animal_category' — no extra metadata typically needed

    lexeme: nullable for content types that are not standard vocabulary
            (verb paradigm forms, prayer lines, etc.)

    sort_order preserves source ordering within a lesson.
    source_notes from JSON are also written to review_flags at import time.
    """

    class ContentType(models.TextChoices):
        VOCABULARY      = 'vocabulary',       'Vocabulary'
        VERB_FORM       = 'verb_form',         'Verb Form'
        VERB_PHRASE     = 'verb_phrase',       'Verb Phrase'
        COLOR_FORM      = 'color_form',        'Color Form'
        COLOR_USAGE     = 'color_usage',       'Color Usage'
        SUFFIX_EXAMPLE  = 'suffix_example',    'Suffix Example'
        SENTENCE        = 'sentence',          'Sentence'
        PRAYER_LINE     = 'prayer_line',       'Prayer Line'
        NUMBER          = 'number',            'Number'
        ANIMAL_CATEGORY = 'animal_category',   'Animal Category'

    lesson       = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='entries')
    lexeme       = models.ForeignKey(
        Lexeme, on_delete=models.SET_NULL, null=True, blank=True, related_name='entries'
    )
    content_type = models.CharField(
        max_length=30, choices=ContentType.choices, default=ContentType.VOCABULARY
    )
    paiute        = models.TextField()
    pronunciation = models.TextField(blank=True, null=True)
    english       = models.TextField()
    context_note  = models.TextField(blank=True, null=True)
    source_notes  = models.TextField(blank=True, null=True)
    sort_order    = models.SmallIntegerField(null=True, blank=True)
    metadata      = models.JSONField(null=True, blank=True)
    embedding     = VectorField(dimensions=1536, null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'entries'
        ordering = ['lesson', 'sort_order']
        indexes  = [
            models.Index(fields=['content_type']),
            models.Index(fields=['lesson', 'content_type']),
        ]

    def __str__(self):
        return f'[{self.content_type}] {self.paiute} -- {self.english}'


# =============================================================================
# GRAMMAR TABLES
# =============================================================================

class VerbParadigmForm(models.Model):
    """
    Conjugated/derived forms within a verb paradigm.
    Paradigms: Tuka (eat, L28), Nadakwunae (jump, L33), Poone (see, L35).

    grammatical_tags JSONB -- all keys optional, omit when not applicable:
    {
        "aspect":         "base"|"progressive"|"past"|"recent_past"|"future"|"near_future"|"inchoative",
        "number":         "singular"|"dual"|"plural",
        "directionality": "none"|"going"|"going_along"|"return"|"come"|"through",
        "continuity":     "none"|"continuous"|"back_and_forth",
        "posture":        "sitting"|"standing"|"laying",    # Poone only
        "modality":       "none"|"try"|"might"|"want"|"ask"|"reason",
        "manner":         "slow"                            # tsagate forms
    }

    ORM query example:
        VerbParadigmForm.objects.filter(grammatical_tags__contains={"aspect": "past"})
    """
    lesson               = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='verb_paradigm_forms')
    base_verb_lexeme     = models.ForeignKey(
        Lexeme, on_delete=models.SET_NULL, null=True, blank=True, related_name='verb_paradigm_forms'
    )
    paiute               = models.TextField()
    pronunciation        = models.TextField(blank=True, null=True)
    english              = models.TextField()
    grammatical_tags     = models.JSONField(null=True, blank=True)
    sort_order           = models.SmallIntegerField(null=True, blank=True)
    source_notes         = models.TextField(blank=True, null=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'verb_paradigm_forms'
        ordering = ['lesson', 'sort_order']

    def __str__(self):
        return f'{self.paiute} -- {self.english}'


class VerbPhraseForm(models.Model):
    """
    Auxiliary phrase forms associated with a verb paradigm lesson.
    e.g. "Too'e Nadakwunaekwu" (try to jump), "Mabe Nadakwunaekwu" (might jump).
    Full multi-word phrases -- not single morphological forms.
    """
    lesson       = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='verb_phrase_forms')
    paiute       = models.TextField()
    english      = models.TextField()
    sort_order   = models.SmallIntegerField(null=True, blank=True)
    source_notes = models.TextField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'verb_phrase_forms'
        ordering = ['lesson', 'sort_order']

    def __str__(self):
        return f'{self.paiute} -- {self.english}'


class ColorForm(models.Model):
    """
    Full color morphology from Disc 3 L22 (Colors).
    One row per color, storing all three grammatical forms plus compound example.

    adjective:  root + -kweta       e.g. Atsakweta
    predicate:  root + -kweta'a     e.g. Atsakweta'a
    noun_form:  root + -kwetadu     e.g. Atsakwetadu

    extra_forms JSONB: additional forms not in the base triad.
        White example: [{"paiute": "Tohataepu", "english": "state of being white / faded"}]

    Compound fields (root onto noun):
        compound_components: "Atsa + Kwasu"
        compound_result:     "Atsakwasu"
        compound_english:    "red shirt"
    """
    lesson              = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='color_forms')
    english             = models.TextField()         # "red", "white", "blue", etc.
    adjective           = models.TextField()         # e.g. "Atsakweta"
    predicate           = models.TextField()         # e.g. "Atsakweta'a"
    predicate_gloss     = models.TextField()         # e.g. "is red"
    noun_form           = models.TextField()         # e.g. "Atsakwetadu"
    noun_gloss          = models.TextField()         # e.g. "red one"
    extra_forms         = models.JSONField(null=True, blank=True)
    compound_components = models.TextField(blank=True, null=True)   # "Atsa + Kwasu"
    compound_result     = models.TextField(blank=True, null=True)   # "Atsakwasu"
    compound_english    = models.TextField(blank=True, null=True)   # "red shirt"
    sort_order          = models.SmallIntegerField(null=True, blank=True)
    source_notes        = models.TextField(blank=True, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'color_forms'
        ordering = ['lesson', 'sort_order']

    def __str__(self):
        return f'{self.english}: {self.adjective}'


class ColorExampleSentence(models.Model):
    """
    Example sentences attached to a color form.
    One ColorForm can have multiple example sentences.
    """
    color_form = models.ForeignKey(ColorForm, on_delete=models.CASCADE, related_name='example_sentences')
    paiute     = models.TextField()
    english    = models.TextField()
    sort_order = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'color_example_sentences'
        ordering = ['color_form', 'sort_order']

    def __str__(self):
        return f'{self.paiute} -- {self.english}'


class ColorApplicationEntry(models.Model):
    """
    Applied color usage from Disc 4 L34 (The Color Red).
    23 phrases/sentences showing Atsakweta in varied grammatical roles.
    Separate from color_forms -- usage examples, not paradigm documentation.
    """
    lesson        = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='color_application_entries')
    source_number = models.SmallIntegerField()
    paiute        = models.TextField()
    english       = models.TextField()
    source_notes  = models.TextField(blank=True, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'color_application_entries'
        ordering = ['lesson', 'source_number']

    def __str__(self):
        return f'#{self.source_number}: {self.paiute}'


class SuffixExample(models.Model):
    """
    Suffix lesson entries from Disc 4 L38-42.
    suffix values: '-kwu', '-hookwu', '-pu', '-ku', '-kooha'

    base_verb_lexeme enables cross-lesson queries:
        SuffixExample.objects.filter(base_verb_lexeme=hebe).order_by('lesson__lesson_number')
        -> all suffix forms for Hebe (drink) across all 5 suffix lessons
    """
    lesson            = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='suffix_examples')
    suffix            = models.CharField(max_length=20)
    base_verb         = models.TextField()
    base_verb_english = models.TextField(blank=True, null=True)
    base_verb_lexeme  = models.ForeignKey(
        Lexeme, on_delete=models.SET_NULL, null=True, blank=True, related_name='suffix_examples'
    )
    suffixed_form     = models.TextField()
    english           = models.TextField()
    sort_order        = models.SmallIntegerField(null=True, blank=True)
    source_notes      = models.TextField(blank=True, null=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'suffix_examples'
        ordering = ['lesson', 'sort_order']

    def __str__(self):
        return f'{self.suffixed_form} ({self.suffix}) -- {self.english}'


class SentenceEntry(models.Model):
    """
    Sentence entries with word-level component glosses.
    Used for:
        Disc 3 L26-27: Paiute W's (what, where, who, when, why, how)
        Disc 4 L43-44: Sentence I & II (Soo/Ka subject-object marking)

    components JSONB preserves word-label annotations from source:
        {"what": "Hemma", "you": "U", "see": "Poone"}
        {"subject_marker": "Soo", "object_marker": "Ka", "verb": "Poone"}

    embedding enables AI tutor semantic search at sentence level.
    """
    lesson       = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='sentence_entries')
    paiute       = models.TextField()
    english      = models.TextField()
    components   = models.JSONField(null=True, blank=True)
    embedding    = VectorField(dimensions=1536, null=True, blank=True)
    sort_order   = models.SmallIntegerField(null=True, blank=True)
    source_notes = models.TextField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sentence_entries'
        ordering = ['lesson', 'sort_order']

    def __str__(self):
        return f'{self.paiute} -- {self.english}'


class PrayerLine(models.Model):
    """
    Food prayer lines from Disc 3 L32, stored line by line.
    is_ritual_action=True on Poowa lines (physical blowing blessings,
    not spoken words). ritual_note documents what the action is.
    """
    lesson           = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='prayer_lines')
    line_number      = models.SmallIntegerField()
    paiute           = models.TextField()
    english          = models.TextField()
    is_ritual_action = models.BooleanField(default=False)
    ritual_note      = models.TextField(blank=True, null=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'prayer_lines'
        ordering = ['lesson', 'line_number']

    def __str__(self):
        return f'L32 line {self.line_number}: {self.paiute}'


class NumberEntry(models.Model):
    """
    Number vocabulary from Disc 2 L21.
    entry_type: 'base' = Sumu'yoo (1) through Naemisa (10)
                'compound' = Naemisatse (11), Sumukadoo'opu (19), etc.
    numeral: integer value for ordered queries and app-side number lookup.
    components: compound breakdown, e.g. "Naemisa + Sumu'yoo"
    """
    ENTRY_TYPE_CHOICES = [('base', 'Base'), ('compound', 'Compound')]

    lesson       = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='number_entries')
    paiute       = models.TextField()
    english      = models.TextField()
    numeral      = models.SmallIntegerField(null=True, blank=True)
    entry_type   = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    components   = models.TextField(blank=True, null=True)
    sort_order   = models.SmallIntegerField(null=True, blank=True)
    source_notes = models.TextField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'number_entries'
        ordering = ['lesson', 'numeral', 'sort_order']

    def __str__(self):
        prefix = f'{self.numeral}: ' if self.numeral else ''
        return f'{prefix}{self.paiute} -- {self.english}'


class AnimalCategory(models.Model):
    """
    Taxon category labels from Disc 2 L14 (Animals continued).
    Category headers (Waterfowl, Raptors, Insects) with Paiute equivalents.
    Individual animal vocabulary items live in entries.
    """
    lesson     = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='animal_categories')
    paiute     = models.TextField()
    english    = models.TextField()
    sort_order = models.SmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'animal_categories'
        ordering = ['lesson', 'sort_order']

    def __str__(self):
        return f'{self.paiute} -- {self.english}'


# =============================================================================
# USERS + PROGRESS
# =============================================================================

class User(models.Model):
    """
    App user. Separate from Django's built-in auth.User for full schema control.
    JWT auth sits on top of this.
    password_hash: bcrypt/argon2 output -- never plaintext.
    tribal_enrollment_number: verifies tribal_member tier access.
    """
    email                    = models.TextField(unique=True)
    password_hash            = models.TextField()
    display_name             = models.TextField(blank=True, null=True)
    role                     = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.PUBLIC
    )
    is_active                = models.BooleanField(default=True)
    tribal_enrollment_number = models.TextField(blank=True, null=True)
    created_at               = models.DateTimeField(auto_now_add=True)
    updated_at               = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email


class UserLessonProgress(models.Model):
    """Lesson-level progress. One row per (user, lesson). completed_at non-null = done."""
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson           = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='user_progress')
    started_at       = models.DateTimeField(null=True, blank=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table        = 'user_lesson_progress'
        unique_together = [('user', 'lesson')]

    def __str__(self):
        return f'{self.user} | {self.lesson}'


class UserEntryReview(models.Model):
    """
    Entry-level spaced repetition (SM-2). One row per (user, entry), updated on each review.
    ease_factor: 1.3-2.5, starts at 2.5, drops on wrong answers
    interval_days: grows exponentially on correct streak
    next_review_at: null until first review completes
    """
    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='entry_reviews')
    entry          = models.ForeignKey(Entry, on_delete=models.PROTECT, related_name='user_reviews')
    reviewed_at    = models.DateTimeField(auto_now=True)
    correct        = models.BooleanField()
    ease_factor    = models.DecimalField(max_digits=4, decimal_places=2, default=2.5)
    interval_days  = models.SmallIntegerField(default=1)
    next_review_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table        = 'user_entry_reviews'
        unique_together = [('user', 'entry')]

    def __str__(self):
        return f'{self.user} | {self.entry} | correct={self.correct}'


# =============================================================================
# REVIEW FLAGS (QA)
# =============================================================================

class ReviewFlag(models.Model):
    """
    Polymorphic QA flag table using Django's ContentType framework.
    Attach flags to any content row across any grammar table.

    Usage:
        # Create a flag on an Entry
        ReviewFlag.objects.create(
            content_type=ContentType.objects.get_for_model(Entry),
            object_id=entry.id,
            flag_note="Source prints Wahamanoyoo without apostrophe -- verify audio",
            source=FlagSource.TRANSCRIPTION,
        )

        # Get flagged object back directly
        flag.content_object   # returns Entry, VerbParadigmForm, etc.

        # All unresolved flags for one entry
        ReviewFlag.objects.filter(
            content_type=ContentType.objects.get_for_model(Entry),
            object_id=entry.id,
            resolved=False,
        )

        # All unresolved flags system-wide
        ReviewFlag.objects.filter(resolved=False).select_related('content_type')

    NOTE: The raw schema uses entity_type TEXT + entity_id INTEGER.
    Django's ContentType framework gives the same pattern with type-safe
    content_object access. Underlying columns are content_type_id + object_id.
    """
    content_type    = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id       = models.PositiveIntegerField()
    content_object  = GenericForeignKey('content_type', 'object_id')

    flag_note       = models.TextField()
    source          = models.CharField(
        max_length=20, choices=FlagSource.choices, default=FlagSource.TRANSCRIPTION
    )
    resolved        = models.BooleanField(default=False)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolved_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_flags'
    )
    resolution_note = models.TextField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_flags'
        indexes  = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        status = 'resolved' if self.resolved else 'open'
        return f'[{status}] {self.content_type} #{self.object_id}: {self.flag_note[:60]}'