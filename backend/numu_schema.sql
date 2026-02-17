-- =============================================================================
-- Numu Yadooape Language Preservation App
-- PostgreSQL Schema
-- =============================================================================
-- Conventions:
--   - All Paiute text stored in Wycliffe spelling; never normalized or anglicized
--   - paiute_normalized = lowercase only, used for dedup matching â€” not display
--   - vector(1536) covers OpenAI text-embedding-3-small and Claude embedding API
--   - content_tier enforced at lesson level; entry-level override available if needed
--   - review_flags is polymorphic â€” entity_type + entity_id reference any table
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- for future UUID needs if any

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE content_tier AS ENUM ('public', 'tribal_member', 'educator', 'admin');

CREATE TYPE user_role AS ENUM ('public', 'tribal_member', 'educator', 'admin');

CREATE TYPE flag_source AS ENUM ('transcription', 'audio', 'import', 'manual');

-- =============================================================================
-- CORE STRUCTURE: discs â†’ lessons â†’ audio_files
-- =============================================================================

CREATE TABLE discs (
    id              SMALLINT    PRIMARY KEY,  -- 1â€“4, matches source disc numbering
    title           TEXT        NOT NULL,
    dialect         TEXT        NOT NULL DEFAULT 'Pyramid Lake Paiute Tribe',
    writing_system  TEXT        NOT NULL DEFAULT 'Wycliffe',
    total_pages     SMALLINT    NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE lessons (
    id              SERIAL          PRIMARY KEY,
    disc_id         SMALLINT        NOT NULL REFERENCES discs(id),
    lesson_number   SMALLINT        NOT NULL UNIQUE,  -- 4â€“44 sequential across all discs
    title           TEXT            NOT NULL,
    category        TEXT            NOT NULL,         -- 'phrases', 'nouns', 'verbs', 'grammar_suffix', etc.
    page            TEXT            NOT NULL,         -- "disc.page" format e.g. "2.5"
    section_title   TEXT,                             -- optional source section header e.g. "Numudooe"
    content_tier    content_tier    NOT NULL DEFAULT 'tribal_member',
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Audio files are currently 1-per-lesson; designed for future per-entry audio
CREATE TABLE audio_files (
    id              SERIAL      PRIMARY KEY,
    filename        TEXT        NOT NULL,             -- original filename from JSON e.g. "4 Introductions and Farewells .m4a"
    s3_key          TEXT,                             -- S3 object key, populated after upload
    duration_seconds SMALLINT,
    lesson_id       INTEGER     REFERENCES lessons(id),
    entry_id        INTEGER,                          -- FK added after entries table exists; see constraint below
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT audio_has_parent CHECK (lesson_id IS NOT NULL OR entry_id IS NOT NULL)
);

-- =============================================================================
-- LEXEME + ENTRY TABLES
-- =============================================================================

-- Canonical Paiute form, independent of context or meaning.
-- Each distinct surface form = one lexeme.
-- Multi-sense words (Numu = people AND liver) share a single lexeme.
-- Auto-resolve at import: get_or_create on paiute_normalized.
CREATE TABLE lexemes (
    id                      SERIAL      PRIMARY KEY,
    paiute                  TEXT        NOT NULL,     -- canonical Wycliffe form, case-preserved
    paiute_normalized       TEXT        NOT NULL UNIQUE, -- lowercase only; used for dedup matching
    is_multi_sense          BOOLEAN     NOT NULL DEFAULT FALSE, -- true when 2+ entries share this lexeme
    needs_lexeme_review     BOOLEAN     NOT NULL DEFAULT FALSE, -- set true by import script on auto-link
    embedding               vector(1536),             -- populated by embedding job; null until then
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Standard vocabulary entries: nouns, verbs (base form only), phrases, pronouns,
-- family terms, clothing, body parts, animals, plants, directions, commands, etc.
-- Also covers: color adjective form (canonical lexeme), number base forms,
-- question sentences without word glosses, and Numma / ha'a phrase lessons.
CREATE TABLE entries (
    id              SERIAL      PRIMARY KEY,
    lesson_id       INTEGER     NOT NULL REFERENCES lessons(id),
    lexeme_id       INTEGER     NOT NULL REFERENCES lexemes(id),
    paiute          TEXT        NOT NULL,             -- exact Wycliffe form from source
    pronunciation   TEXT,                             -- syllable breakdown e.g. "Kwa-su"
    english         TEXT        NOT NULL,
    context_note    TEXT,                             -- speaker context e.g. "man speaking", "talking to two persons"
    source_notes    TEXT,                             -- inline notes from JSON source
    sort_order      SMALLINT,                         -- preserves source ordering within lesson
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add deferred FK for audio_files.entry_id now that entries exists
ALTER TABLE audio_files ADD CONSTRAINT fk_audio_entry
    FOREIGN KEY (entry_id) REFERENCES entries(id);

-- =============================================================================
-- GRAMMAR TABLES
-- =============================================================================

-- Verb paradigm forms for Tuka (L28), Nadakwunae (L33), Poone (L35).
-- grammatical_tags JSONB schema (all keys optional, null means not applicable):
--   aspect:        "base" | "progressive" | "past" | "recent_past" |
--                  "future" | "near_future" | "inchoative"
--   number:        "singular" | "dual" | "plural"
--   directionality:"none" | "going" | "going_along" | "return" | "come" | "through"
--   continuity:    "none" | "continuous" | "back_and_forth"
--   posture:       "sitting" | "standing" | "laying"   (Poone-specific)
--   modality:      "none" | "try" | "might" | "want" | "ask" | "reason"
--   manner:        "slow"                              (tsagate forms)
CREATE TABLE verb_paradigm_forms (
    id                  SERIAL      PRIMARY KEY,
    lesson_id           INTEGER     NOT NULL REFERENCES lessons(id),
    base_verb_lexeme_id INTEGER     REFERENCES lexemes(id),  -- FK to the base verb (Tuka, Nadakwunae, Poone)
    paiute              TEXT        NOT NULL,
    pronunciation       TEXT,
    english             TEXT        NOT NULL,
    grammatical_tags    JSONB,
    sort_order          SMALLINT,
    source_notes        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auxiliary phrase forms that modify a verb paradigm (e.g. "Too'e Nadakwunaekwu" = try to jump).
-- Separate from paradigm forms because the Paiute unit is the full phrase, not a single morphological form.
CREATE TABLE verb_phrase_forms (
    id          SERIAL      PRIMARY KEY,
    lesson_id   INTEGER     NOT NULL REFERENCES lessons(id),
    paiute      TEXT        NOT NULL,    -- full phrase including auxiliary word
    english     TEXT        NOT NULL,
    sort_order  SMALLINT,
    source_notes TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Color morphology triads from Disc 3 L22 (Colors).
-- One row per color; stores all three grammatical forms and the compound example.
-- extra_forms JSONB for colors with additional forms (e.g. white's Tohataepu = faded/white state).
CREATE TABLE color_forms (
    id                  SERIAL      PRIMARY KEY,
    lesson_id           INTEGER     NOT NULL REFERENCES lessons(id),
    english             TEXT        NOT NULL,           -- "red", "white", "blue", etc.
    adjective           TEXT        NOT NULL,           -- e.g. "Atsakweta"
    predicate           TEXT        NOT NULL,           -- e.g. "Atsakweta'a"
    predicate_gloss     TEXT        NOT NULL,           -- "is red"
    noun_form           TEXT        NOT NULL,           -- e.g. "Atsakwetadu"
    noun_gloss          TEXT        NOT NULL,           -- "red one"
    extra_forms         JSONB,                          -- [{"paiute": "Tohataepu", "english": "state of being white / faded"}]
    compound_components TEXT,                           -- "Atsa + Kwasu"
    compound_result     TEXT,                           -- "Atsakwasu"
    compound_english    TEXT,                           -- "red shirt"
    sort_order          SMALLINT,
    source_notes        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Example sentences attached to a color form
CREATE TABLE color_example_sentences (
    id              SERIAL      PRIMARY KEY,
    color_form_id   INTEGER     NOT NULL REFERENCES color_forms(id) ON DELETE CASCADE,
    paiute          TEXT        NOT NULL,
    english         TEXT        NOT NULL,
    sort_order      SMALLINT
);

-- Applied color entries from Disc 4 L34 (The Color Red).
-- Numbered phrases/sentences demonstrating the red root in varied grammatical roles.
-- Stored separately from color_forms because these are usage examples, not paradigm documentation.
CREATE TABLE color_application_entries (
    id          SERIAL      PRIMARY KEY,
    lesson_id   INTEGER     NOT NULL REFERENCES lessons(id),
    source_number SMALLINT  NOT NULL,   -- original numbering from source (1â€“23)
    paiute      TEXT        NOT NULL,
    english     TEXT        NOT NULL,
    source_notes TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Suffix lesson examples from Disc 4 L38â€“L42 (-kwu, -hookwu, -pu, -ku, -kooha).
-- suffix and suffix_meaning stored redundantly here for query convenience;
-- canonical suffix metadata lives on the lesson row.
CREATE TABLE suffix_examples (
    id                  SERIAL      PRIMARY KEY,
    lesson_id           INTEGER     NOT NULL REFERENCES lessons(id),
    suffix              TEXT        NOT NULL,   -- "-kwu", "-hookwu", "-pu", "-ku", "-kooha"
    base_verb           TEXT        NOT NULL,   -- e.g. "Hebe"
    base_verb_english   TEXT,                   -- e.g. "drink"
    base_verb_lexeme_id INTEGER     REFERENCES lexemes(id),
    suffixed_form       TEXT        NOT NULL,   -- e.g. "Hebekwu"
    english             TEXT        NOT NULL,   -- e.g. "going to drink"
    sort_order          SMALLINT,
    source_notes        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sentence entries with word-level component glosses.
-- Used for: Disc 3 Paiute W's (L26â€“27), Disc 4 Sentence I & II (L43â€“44).
-- components JSONB: word-label annotations from source
--   e.g. {"what": "Hemma", "you": "U", "see": "Poone"}
--   or   {"subject_marker": "Soo", "object_marker": "Ka"}
-- Sentences get their own embedding column â€” semantic search at sentence level
-- is valuable for the AI tutor ("find a sentence that asks about ownership").
CREATE TABLE sentence_entries (
    id          SERIAL      PRIMARY KEY,
    lesson_id   INTEGER     NOT NULL REFERENCES lessons(id),
    paiute      TEXT        NOT NULL,
    english     TEXT        NOT NULL,
    components  JSONB,
    embedding   vector(1536),
    sort_order  SMALLINT,
    source_notes TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Food prayer lines from Disc 3 L32.
-- is_ritual_action flags Poowa lines (ritual blowing blessing) â€”
-- these are physical actions, not spoken words, but appear in the prayer sequence.
CREATE TABLE prayer_lines (
    id                  SERIAL      PRIMARY KEY,
    lesson_id           INTEGER     NOT NULL REFERENCES lessons(id),
    line_number         SMALLINT    NOT NULL,
    paiute              TEXT        NOT NULL,
    english             TEXT        NOT NULL,
    is_ritual_action    BOOLEAN     NOT NULL DEFAULT FALSE,
    ritual_note         TEXT,                   -- e.g. "ritual blowing blessing performed here"
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Number entries from Disc 2 L21.
-- base: Sumu'yoo (1), Waha'yoo (2), etc.
-- compound: Naemisatse (11) = Naemisa (10) + Sumu'yoo (1), etc.
-- numeral column enables ordered queries and app-side number lookup.
CREATE TABLE number_entries (
    id              SERIAL      PRIMARY KEY,
    lesson_id       INTEGER     NOT NULL REFERENCES lessons(id),
    paiute          TEXT        NOT NULL,
    english         TEXT        NOT NULL,
    numeral         SMALLINT,               -- actual integer value; null for non-numeric entries
    entry_type      TEXT        NOT NULL CHECK (entry_type IN ('base', 'compound')),
    components      TEXT,                   -- compound breakdown e.g. "Naemisa + Sumu'yoo"
    sort_order      SMALLINT,
    source_notes    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Animal category terms from Disc 2 L14 (Animals continued).
-- Separate from entries because these are taxon labels, not vocabulary items.
-- e.g. "Waterfowl", "Raptors", "Insects" with their Paiute equivalents.
CREATE TABLE animal_categories (
    id          SERIAL      PRIMARY KEY,
    lesson_id   INTEGER     NOT NULL REFERENCES lessons(id),
    paiute      TEXT        NOT NULL,
    english     TEXT        NOT NULL,
    sort_order  SMALLINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- USERS + PROGRESS
-- =============================================================================

CREATE TABLE users (
    id                          SERIAL      PRIMARY KEY,
    email                       TEXT        NOT NULL UNIQUE,
    password_hash               TEXT        NOT NULL,
    display_name                TEXT,
    role                        user_role   NOT NULL DEFAULT 'public',
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    tribal_enrollment_number    TEXT,       -- for tribal_member tier verification; nullable
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lesson-level progress tracking
CREATE TABLE user_lesson_progress (
    id              SERIAL      PRIMARY KEY,
    user_id         INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id       INTEGER     NOT NULL REFERENCES lessons(id),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    last_accessed_at TIMESTAMPTZ,
    UNIQUE (user_id, lesson_id)
);

-- Entry-level spaced repetition data (SM-2 algorithm).
-- Drives the flashcard / quiz review queue.
-- ease_factor: 1.3â€“2.5 range; starts at 2.5; decreases on incorrect answers
-- interval_days: grows exponentially on correct streak
CREATE TABLE user_entry_reviews (
    id              SERIAL          PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_id        INTEGER         NOT NULL REFERENCES entries(id),
    reviewed_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    correct         BOOLEAN         NOT NULL,
    ease_factor     NUMERIC(4,2)    NOT NULL DEFAULT 2.5,
    interval_days   SMALLINT        NOT NULL DEFAULT 1,
    next_review_at  TIMESTAMPTZ,
    UNIQUE (user_id, entry_id)
);

-- =============================================================================
-- REVIEW FLAGS (QA)
-- =============================================================================

-- Polymorphic flag table. entity_type is the table name; entity_id is its PK.
-- Valid entity_type values:
--   'entries', 'verb_paradigm_forms', 'verb_phrase_forms', 'suffix_examples',
--   'color_forms', 'color_application_entries', 'sentence_entries',
--   'prayer_lines', 'number_entries', 'lexemes', 'lessons'
-- All flags from JSON source_notes are imported here at load time.
-- Resolved flags retain their resolution note for audit trail.
CREATE TABLE review_flags (
    id              SERIAL          PRIMARY KEY,
    entity_type     TEXT            NOT NULL,
    entity_id       INTEGER         NOT NULL,
    flag_note       TEXT            NOT NULL,
    source          flag_source     NOT NULL DEFAULT 'transcription',
    resolved        BOOLEAN         NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    resolved_by     INTEGER         REFERENCES users(id),
    resolution_note TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Lexeme lookup and dedup
CREATE INDEX idx_lexemes_paiute_normalized ON lexemes(paiute_normalized);
CREATE INDEX idx_lexemes_needs_review ON lexemes(needs_lexeme_review)
    WHERE needs_lexeme_review = TRUE;
CREATE INDEX idx_lexemes_multi_sense ON lexemes(is_multi_sense)
    WHERE is_multi_sense = TRUE;

-- Entry lookups
CREATE INDEX idx_entries_lesson_id ON entries(lesson_id);
CREATE INDEX idx_entries_lexeme_id ON entries(lexeme_id);

-- Verb paradigm JSONB tag queries
-- Supports queries like: WHERE grammatical_tags @> '{"aspect": "past"}'
CREATE INDEX idx_verb_paradigm_tags ON verb_paradigm_forms USING gin(grammatical_tags);
CREATE INDEX idx_verb_paradigm_lesson ON verb_paradigm_forms(lesson_id);
CREATE INDEX idx_verb_paradigm_base_verb ON verb_paradigm_forms(base_verb_lexeme_id);

-- Suffix example lookups (cross-lesson paradigm table view)
CREATE INDEX idx_suffix_examples_suffix ON suffix_examples(suffix);
CREATE INDEX idx_suffix_examples_lesson ON suffix_examples(lesson_id);
CREATE INDEX idx_suffix_examples_base_verb_lexeme ON suffix_examples(base_verb_lexeme_id);

-- Sentence entries
CREATE INDEX idx_sentence_entries_lesson ON sentence_entries(lesson_id);

-- Review flags â€” primary query pattern is "all unresolved flags for a given entity"
CREATE INDEX idx_review_flags_entity ON review_flags(entity_type, entity_id);
CREATE INDEX idx_review_flags_unresolved ON review_flags(entity_type, entity_id)
    WHERE resolved = FALSE;

-- User progress
CREATE INDEX idx_user_lesson_progress_user ON user_lesson_progress(user_id);
CREATE INDEX idx_user_entry_reviews_user ON user_entry_reviews(user_id);
CREATE INDEX idx_user_entry_reviews_next_review ON user_entry_reviews(user_id, next_review_at)
    WHERE next_review_at IS NOT NULL;

-- pgvector similarity search indexes (IVFFlat; build after embeddings are populated)
-- lists=100 is appropriate for ~800 lexemes. Re-evaluate if corpus grows significantly.
-- CREATE INDEX idx_lexemes_embedding ON lexemes
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_sentence_entries_embedding ON sentence_entries
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- NOTE: IVFFlat indexes require data to exist before they can be built.
--       Uncomment and run these after the embedding job has populated the columns.

-- =============================================================================
-- SEED: discs
-- =============================================================================

INSERT INTO discs (id, title, total_pages, notes) VALUES
(1, 'Numu Yadooape Disc 1', 14, 'Lessons 4â€“12. Introductions, pronouns, nouns, verbs, family, clothing. Contains full Wycliffe writing system reference.'),
(2, 'Numu Yadooape Disc 2', 14, 'Lessons 13â€“21. Animals, trees/plants, astronomy, weather, directions, body parts, numbers.'),
(3, 'Numu Yadooape Disc 3', 13, 'Lessons 22â€“32. Colors (full morphology), cradleboard, helping words, commands, questions, eating paradigm, food/utensils, food prayer.'),
(4, 'Numu Yadooape Disc 4', 14, 'Lessons 33â€“44. Verb paradigms (jump, see), color red application, body conditions, yes/no questions, five suffix lessons, sentence structure.');
