# Numu Yadooape — Django Setup Guide (Scratch to Import-Ready)

## Prerequisites (already done)
- PostgreSQL 16 running via Homebrew
- `numu_db` created, schema loaded (19 tables + indexes + disc seed rows)
- pgvector extension installed and enabled on `numu_db`
- DB user: `pmatson` with full privileges on `numu_db`

---

## Phase 1 — Python Environment

### 1.1 Check Python version
```bash
python3 --version
```
You need 3.11+. If you're on an older version, install via pyenv:
```bash
brew install pyenv
pyenv install 3.12.3
pyenv global 3.12.3
```

### 1.2 Create project directory and virtual environment
```bash
mkdir ~/projects/numu_yadooape
cd ~/projects/numu_yadooape
python3 -m venv venv
source venv/bin/activate
```

You'll activate this venv every time you work on the project:
```bash
source ~/projects/numu_yadooape/venv/bin/activate
```

### 1.3 Install dependencies
```bash
pip install \
  django \
  djangorestframework \
  psycopg2-binary \
  pgvector \
  djangorestframework-simplejwt \
  python-dotenv
```

Freeze immediately:
```bash
pip freeze > requirements.txt
```

---

## Phase 2 — Django Project Scaffold

### 2.1 Create the project
Run this from `~/projects/numu_yadooape/`:
```bash
django-admin startproject config .
```

The `.` puts settings directly in the current directory. Your structure will be:
```
numu_yadooape/
├── venv/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── manage.py
└── requirements.txt
```

### 2.2 Create the numu app
```bash
python manage.py startapp numu
```

Structure after this:
```
numu_yadooape/
├── venv/
├── config/
├── numu/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── migrations/
│   │   └── __init__.py
│   ├── models.py       <-- replace this with our models.py
│   ├── tests.py
│   └── views.py
├── manage.py
└── requirements.txt
```

### 2.3 Place the models file
Copy `models.py` (the one we finalized) into `numu/models.py`, replacing the empty one Django generated.

---

## Phase 3 — Environment Variables

Never put credentials in settings.py. Use a `.env` file.

### 3.1 Create .env
```bash
touch .env
```

Contents:
```
DATABASE_NAME=numu_db
DATABASE_USER=pmatson
DATABASE_PASSWORD=
DATABASE_HOST=localhost
DATABASE_PORT=5432
SECRET_KEY=replace-this-with-a-long-random-string
DEBUG=True
```

For `DATABASE_PASSWORD`: if your `pmatson` user has no password set (local socket auth), leave it empty. If you set one during DB setup, put it here.

Generate a proper SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3.2 Add .env to .gitignore
```bash
echo ".env" >> .gitignore
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

---

## Phase 4 — settings.py

Replace the contents of `config/settings.py` with:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',   # required for ReviewFlag GenericForeignKey
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'pgvector.django',               # pgvector field support
    'numu',                          # our app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'numu_db'),
        'USER': os.getenv('DATABASE_USER', 'pmatson'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', ''),
        'HOST': os.getenv('DATABASE_HOST', 'localhost'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Los_Angeles'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
```

---

## Phase 5 — Fix One Schema Mismatch (review_flags)

**This must be done before migrations.**

The `review_flags` table in your live schema has columns `entity_type TEXT` and `entity_id INTEGER`. Our Django model uses the ContentType framework, which expects `content_type_id INTEGER` (FK to `django_content_type`) and `object_id INTEGER`. These don't match — the table needs to be updated to work with our model.

Since `review_flags` is empty right now, this is a safe schema change.

Connect to psql as pdogg (superuser not needed here, pmatson works):
```bash
psql -U pmatson -d numu_db
```

Run:
```sql
-- Drop the old columns and add the ContentType-compatible ones
ALTER TABLE review_flags
    DROP COLUMN entity_type,
    DROP COLUMN entity_id,
    ADD COLUMN content_type_id INTEGER REFERENCES django_content_type(id),
    ADD COLUMN object_id INTEGER;

-- Update existing indexes (entity columns are gone, add new ones)
DROP INDEX IF EXISTS idx_review_flags_entity;
DROP INDEX IF EXISTS idx_review_flags_unresolved;

CREATE INDEX idx_review_flags_entity ON review_flags(content_type_id, object_id);
CREATE INDEX idx_review_flags_unresolved ON review_flags(content_type_id, object_id)
    WHERE resolved = FALSE;
```

**Wait:** `django_content_type` table doesn't exist yet until you run migrations in Phase 6.
Run the first two migration steps in Phase 6 first, then come back and run these ALTER TABLE statements.
The order will be called out clearly in Phase 6.

---

## Phase 6 — Migrations

This is the most important phase. Your 19 numu tables already exist in the DB — Django must NOT try to recreate them. Django's own internal tables (auth, contenttypes, sessions, admin) do NOT exist yet and should be created normally.

### 6.1 Run Django's built-in migrations first
```bash
python manage.py migrate
```

This creates: `django_migrations`, `django_content_type`, `auth_permission`, `auth_group`, `auth_user`, `django_session`, `django_admin_log`. None of these conflict with your numu tables.

### 6.2 Now run the review_flags ALTER TABLE
Go back to psql and run the ALTER TABLE statements from Phase 5 now that `django_content_type` exists.

```bash
psql -U pmatson -d numu_db
```

```sql
ALTER TABLE review_flags
    DROP COLUMN entity_type,
    DROP COLUMN entity_id,
    ADD COLUMN content_type_id INTEGER REFERENCES django_content_type(id),
    ADD COLUMN object_id INTEGER;

DROP INDEX IF EXISTS idx_review_flags_entity;
DROP INDEX IF EXISTS idx_review_flags_unresolved;

CREATE INDEX idx_review_flags_entity ON review_flags(content_type_id, object_id);
CREATE INDEX idx_review_flags_unresolved ON review_flags(content_type_id, object_id)
    WHERE resolved = FALSE;
```

### 6.3 Generate the numu app migration
```bash
python manage.py makemigrations numu
```

This creates `numu/migrations/0001_initial.py`. Django now knows what the numu schema looks like. It wants to CREATE all 19 tables — but they already exist.

### 6.4 Fake the initial numu migration
```bash
python manage.py migrate numu --fake-initial
```

`--fake-initial` tells Django: "mark this migration as applied without executing the SQL." Django will check that the tables already exist before faking — if any table is missing it will error, which is a useful safety check.

### 6.5 Verify migration state
```bash
python manage.py showmigrations
```

Every migration should show `[X]` (applied). If anything shows `[ ]` (pending), investigate before proceeding.

---

## Phase 7 — Verify the Setup

### 7.1 Check Django can connect and see the tables
```bash
python manage.py shell
```

In the shell:
```python
from numu.models import Disc, Lesson, Lexeme, Entry
print(Disc.objects.count())    # should be 4 (seeded)
print(Lesson.objects.count())  # should be 0 (not imported yet)
print(Lexeme.objects.count())  # should be 0
print(Entry.objects.count())   # should be 0
exit()
```

Expected output: `4`, `0`, `0`, `0`. If Disc returns 4, Django is reading the live DB correctly.

### 7.2 Check model relationships
```python
from numu.models import Disc
d = Disc.objects.get(id=1)
print(d.title)     # "Numu Yadooape Disc 1"
print(d.lessons.count())   # 0 — lessons not imported yet
```

### 7.3 Confirm vector field is recognized
```python
from numu.models import Lexeme
import inspect
print(Lexeme._meta.get_field('embedding'))
# Should print: <pgvector.django.vector.VectorField: embedding>
```

---

## Phase 8 — JSON Import Management Command

### 8.1 Create the management command directory structure
```bash
mkdir -p numu/management/commands
touch numu/management/__init__.py
touch numu/management/commands/__init__.py
touch numu/management/commands/import_discs.py
```

### 8.2 What the command needs to do
This is what we'll build together in the next session. High-level logic:

```
For each disc JSON file (disc1 → disc4):
  Read meta block → verify disc exists in DB
  For each lesson:
    Create Lesson row (lesson_number, title, category, page, disc_id)
    Create AudioFile row linked to the lesson
    
    Detect lesson type by checking which array keys are present:
      → "entries"                 → import to entries table
      → "verb_forms"              → import to verb_paradigm_forms
      → "phrase_forms"            → import to verb_phrase_forms
      → "eating_related_states"   → import to entries (same table)
      → "color_entries"           → import to color_forms + color_example_sentences
      → "color_application_entries" → import to color_application_entries
      → "suffix_entries"          → import to suffix_examples
      → "sentence_entries"        → import to sentence_entries
      → "prayer_lines"            → import to prayer_lines
      → "base_numbers" / "compound_numbers" → import to number_entries
      → "animal_categories"       → import to animal_categories

    For every entry that maps to the entries table:
      Lexeme.objects.get_or_create(paiute_normalized=paiute.lower())
      If created=True → needs_lexeme_review=True
      Create Entry row

    For any entry with source_notes:
      Create ReviewFlag row pointing to that entry

Run in a transaction — all-or-nothing per disc, or wrap the whole import.
Print a summary at the end: N lessons, N entries, N lexemes created, N flags raised.
```

Command invocation will be:
```bash
python manage.py import_discs                    # import all 4 discs
python manage.py import_discs --disc 1           # import one disc only
python manage.py import_discs --dry-run          # validate without writing
```

### 8.3 We'll write this code together next session.

---

## Phase 9 — Post-Import Verification

After the import runs, verify counts in the shell:

```python
from numu.models import *
print(f"Discs:                    {Disc.objects.count()}")           # 4
print(f"Lessons:                  {Lesson.objects.count()}")         # 41
print(f"Audio files:              {AudioFile.objects.count()}")       # ~41
print(f"Lexemes:                  {Lexeme.objects.count()}")         # ~500-700
print(f"Entries:                  {Entry.objects.count()}")          # ~500-600
print(f"Verb paradigm forms:      {VerbParadigmForm.objects.count()}")  # ~54
print(f"Verb phrase forms:        {VerbPhraseForm.objects.count()}")    # ~8
print(f"Color forms:              {ColorForm.objects.count()}")       # ~12
print(f"Color app entries:        {ColorApplicationEntry.objects.count()}") # 23
print(f"Suffix examples:          {SuffixExample.objects.count()}")   # ~101
print(f"Sentence entries:         {SentenceEntry.objects.count()}")   # ~25
print(f"Prayer lines:             {PrayerLine.objects.count()}")       # ~20
print(f"Number entries:           {NumberEntry.objects.count()}")     # ~50
print(f"Animal categories:        {AnimalCategory.objects.count()}")  # ~10
print(f"Review flags:             {ReviewFlag.objects.count()}")      # ~30-40
print(f"Needs lexeme review:      {Lexeme.objects.filter(needs_lexeme_review=True).count()}")
print(f"Multi-sense lexemes:      {Lexeme.objects.filter(is_multi_sense=True).count()}")
```

Also spot-check a known entry:
```python
# Verify a known Paiute word came through clean
Entry.objects.filter(paiute="Kwasu").values('paiute', 'english', 'lesson__title')
```

---

## Phase 10 — Assign grammatical_tags to Verb Paradigm Forms

After import, the ~54 verb paradigm rows will exist with `grammatical_tags=null`.
We'll do this as a separate step using a SQL insert/update block or a second
management command. I'll generate the full JSONB tag data for all three paradigms
(Tuka/Nadakwunae/Poone) once the rows exist and we can see the IDs.

```bash
python manage.py shell
from numu.models import VerbParadigmForm, Lesson
tuka_lesson = Lesson.objects.get(lesson_number=28)
VerbParadigmForm.objects.filter(lesson=tuka_lesson).values('id', 'paiute', 'english')
# paste output to Claude → I'll produce the update SQL
```

---

## Phase 11 — Embedding Job

After data is in place, run an embedding job to populate the `vector(1536)` columns on
`lexemes` and `sentence_entries`. We'll write this as a management command too:

```bash
python manage.py generate_embeddings --model openai  # or --model claude
```

This will:
  - Pull all Lexeme rows where embedding IS NULL
  - Batch call the embedding API (OpenAI text-embedding-3-small or Anthropic)
  - Save the 1536-dim vector back to each row
  - Same for SentenceEntry rows

We'll build this in a later session. You'll need an OpenAI API key or Anthropic API key set in .env.

---

## Phase 12 — IVFFlat Indexes

After embeddings are populated, build the vector similarity indexes.
They're already in the schema as commented-out SQL — just uncomment and run:

```sql
CREATE INDEX idx_lexemes_embedding ON lexemes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_sentence_entries_embedding ON sentence_entries
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

Run these in psql. They take a few seconds on this dataset size.

After this, semantic similarity queries are indexed:
```sql
SELECT paiute, english FROM lexemes
ORDER BY embedding <=> '[0.023, -0.015, ...]'::vector
LIMIT 10;
```

---

## End State — "Django Done" Checklist

- [ ] venv active, dependencies installed, requirements.txt committed
- [ ] `.env` configured, `.gitignore` set
- [ ] `config/settings.py` configured with DB, INSTALLED_APPS, DRF
- [ ] `numu/models.py` in place (22 classes, 19 DB tables)
- [ ] `review_flags` schema updated (entity_type/id → content_type_id/object_id)
- [ ] Django built-in migrations applied (`python manage.py migrate`)
- [ ] Numu app migration faked (`python manage.py migrate numu --fake-initial`)
- [ ] Shell verification: `Disc.objects.count()` returns 4
- [ ] Import command written and tested
- [ ] All 41 lessons imported, row counts verified
- [ ] grammatical_tags assigned to ~54 verb paradigm rows
- [ ] Embedding job run, vector columns populated
- [ ] IVFFlat indexes built
