// src/App.js
import React, { useEffect, useState } from 'react';
import { fetchEntries, fetchLessons } from './api';
import LexemeBrowser from './LexemeBrowser';

function App() {
  // Which main view is active: 'entries' or 'lexemes'
  const [viewMode, setViewMode] = useState('entries'); // 'entries' | 'lexemes'

  // Entries / lessons state (used in the Entries view)
  const [entries, setEntries] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [selectedLessonId, setSelectedLessonId] = useState(''); // '' = all lessons

  const [loadingEntries, setLoadingEntries] = useState(true);
  const [loadingLessons, setLoadingLessons] = useState(true);
  const [error, setError] = useState(null);

  // Load lessons once on mount
  useEffect(() => {
    let cancelled = false;

    async function loadLessons() {
      try {
        setLoadingLessons(true);
        const data = await fetchLessons(); // expects DRF list: { results: [...] }
        if (!cancelled) {
          setLessons(data.results || []);
        }
      } catch (err) {
        console.error('Error fetching lessons:', err);
        if (!cancelled) {
          setError(err.message || 'Error loading lessons');
        }
      } finally {
        if (!cancelled) {
          setLoadingLessons(false);
        }
      }
    }

    loadLessons();
    return () => {
      cancelled = true;
    };
  }, []);

  // Load entries whenever selectedLessonId changes
  useEffect(() => {
    let cancelled = false;

    async function loadEntries() {
      try {
        setLoadingEntries(true);
        setError(null);

        const params = {};
        if (selectedLessonId) {
          params.lesson = selectedLessonId;
        }

        const data = await fetchEntries(params); // { count, next, previous, results }
        if (!cancelled) {
          setEntries(data.results || []);
        }
      } catch (err) {
        console.error('Error fetching entries:', err);
        if (!cancelled) {
          setError(err.message || 'Error loading entries');
        }
      } finally {
        if (!cancelled) {
          setLoadingEntries(false);
        }
      }
    }

    loadEntries();
    return () => {
      cancelled = true;
    };
  }, [selectedLessonId]);

  const handleLessonChange = (e) => {
    setSelectedLessonId(e.target.value);
  };

  const isLoading = loadingEntries || loadingLessons;

  return (
    <div style={{ padding: '1rem', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      <header style={{ marginBottom: '1rem' }}>
        <h1 style={{ margin: 0 }}>Numu Prototype</h1>
        <p style={{ margin: '0.25rem 0 0', color: '#555' }}>
          Browse entries or dictionary lexemes from the Django API.
        </p>
      </header>

      {/* View toggle */}
      <div style={{ marginBottom: '1rem' }}>
        <button
          type="button"
          onClick={() => setViewMode('entries')}
          style={{
            padding: '0.4rem 0.8rem',
            marginRight: '0.5rem',
            borderRadius: '0.25rem',
            border: viewMode === 'entries' ? '2px solid #0070f3' : '1px solid #ccc',
            backgroundColor: viewMode === 'entries' ? '#e6f0ff' : '#f8f8f8',
            cursor: 'pointer',
          }}
        >
          Entries by lesson
        </button>

        <button
          type="button"
          onClick={() => setViewMode('lexemes')}
          style={{
            padding: '0.4rem 0.8rem',
            borderRadius: '0.25rem',
            border: viewMode === 'lexemes' ? '2px solid #0070f3' : '1px solid #ccc',
            backgroundColor: viewMode === 'lexemes' ? '#e6f0ff' : '#f8f8f8',
            cursor: 'pointer',
          }}
        >
          Dictionary (lexemes)
        </button>
      </div>

      {/* ENTRIES VIEW */}
      {viewMode === 'entries' && (
        <>
          {/* Lesson selector */}
          <section
            style={{
              marginBottom: '1rem',
              padding: '0.75rem 1rem',
              borderRadius: '0.5rem',
              border: '1px solid #ddd',
              backgroundColor: '#fafafa',
            }}
          >
            <label
              htmlFor="lesson-select"
              style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}
            >
              Filter by lesson
            </label>

            <select
              id="lesson-select"
              value={selectedLessonId}
              onChange={handleLessonChange}
              disabled={loadingLessons}
              style={{
                minWidth: '260px',
                padding: '0.4rem 0.6rem',
                borderRadius: '0.25rem',
                border: '1px solid #ccc',
                fontSize: '0.95rem',
              }}
            >
              <option value="">All lessons</option>
              {lessons
                .slice()
                .sort((a, b) => a.lesson_number - b.lesson_number)
                .map((lesson) => {
                  const disc = lesson.disc;
                  const lessonLabel = `L${lesson.lesson_number}: ${lesson.title}`;
                  const discLabel = disc ? `Disc ${disc.id}` : '';
                  return (
                    <option key={lesson.id} value={lesson.id}>
                      {lessonLabel}
                      {discLabel ? ` — ${discLabel}` : ''}
                    </option>
                  );
                })}
            </select>
          </section>

          {/* Loading / error states */}
          {isLoading && (
            <div style={{ padding: '0.5rem 0' }}>
              Loading {loadingLessons ? 'lessons…' : 'entries…'}
            </div>
          )}
          {error && (
            <div style={{ padding: '0.5rem 0', color: 'red' }}>
              Error: {error}
            </div>
          )}

          {/* Entries list */}
          {!isLoading && !error && (
            <section>
              <ul style={{ listStyle: 'none', paddingLeft: 0, margin: 0 }}>
                {entries.map((entry) => {
                  const lesson = entry.lesson;
                  const disc = lesson?.disc;

                  const lessonLabel = lesson
                    ? `L${lesson.lesson_number}: ${lesson.title}`
                    : 'Unknown lesson';
                  const discLabel = disc
                    ? `Disc ${disc.id}: ${disc.title}`
                    : null;

                  return (
                    <li
                      key={entry.id}
                      style={{
                        borderBottom: '1px solid #eee',
                        padding: '0.65rem 0',
                      }}
                    >
                      <div style={{ fontSize: '1rem' }}>
                        <strong>{entry.paiute}</strong>
                        {entry.pronunciation && (
                          <span
                            style={{
                              marginLeft: '0.5rem',
                              color: '#666',
                              fontSize: '0.9em',
                            }}
                          >
                            [{entry.pronunciation}]
                          </span>
                        )}
                      </div>

                      <div style={{ marginTop: '0.15rem' }}>{entry.english}</div>

                      <div
                        style={{
                          fontSize: '0.85em',
                          color: '#555',
                          marginTop: '0.25rem',
                        }}
                      >
                        {lessonLabel}
                        {discLabel && <> — {discLabel}</>}
                      </div>

                      {entry.context_note && (
                        <div
                          style={{
                            fontSize: '0.8em',
                            color: '#777',
                            marginTop: '0.25rem',
                          }}
                        >
                          Context: {entry.context_note}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>

              {entries.length === 0 && (
                <div style={{ marginTop: '0.5rem', color: '#666' }}>
                  No entries found for this selection.
                </div>
              )}
            </section>
          )}
        </>
      )}

      {/* LEXEME DICTIONARY VIEW */}
      {viewMode === 'lexemes' && (
        <LexemeBrowser />
      )}
    </div>
  );
}

export default App;
