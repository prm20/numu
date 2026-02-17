import React, { useEffect, useState } from 'react';
import { fetchLexemes, fetchLexemeDetail } from './api';

function LexemeBrowser() {
  const [q, setQ] = useState('');
  const [lexemes, setLexemes] = useState([]);
  const [selectedLexeme, setSelectedLexeme] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState(null);

  // fetch list when q changes
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchLexemes(q ? { q } : {});
        if (!cancelled) setLexemes(data.results || []);
      } catch (e) {
        if (!cancelled) setError(e.message || 'Error loading lexemes');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [q]);

  const handleSelectLexeme = async (lexeme) => {
    setSelectedLexeme(null);
    setLoadingDetail(true);
    try {
      const detail = await fetchLexemeDetail(lexeme.id);
      setSelectedLexeme(detail);
    } catch (e) {
      setError(e.message || 'Error loading lexeme detail');
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h1>Numu Dictionary</h1>

      <div style={{ margin: '0.75rem 0' }}>
        <input
          type="search"
          placeholder="Search Paiute or English…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{
            width: '100%',
            maxWidth: 360,
            padding: '0.4rem 0.6rem',
            borderRadius: '0.25rem',
            border: '1px solid #ccc',
          }}
        />
      </div>

      {loading && <div>Loading lexemes…</div>}
      {error && <div style={{ color: 'red' }}>Error: {error}</div>}

      <div style={{ display: 'flex', gap: '1.5rem' }}>
        {/* left: list */}
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, flex: 1 }}>
          {lexemes.map((lex) => (
            <li
              key={lex.id}
              onClick={() => handleSelectLexeme(lex)}
              style={{
                padding: '0.4rem 0',
                borderBottom: '1px solid #eee',
                cursor: 'pointer',
              }}
            >
              <strong>{lex.paiute}</strong>
              {lex.needs_lexeme_review && (
                <span style={{ marginLeft: 8, fontSize: '0.8em', color: '#b55' }}>
                  (needs review)
                </span>
              )}
            </li>
          ))}
          {!loading && lexemes.length === 0 && (
            <li style={{ color: '#666' }}>No results.</li>
          )}
        </ul>

        {/* right: detail */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {loadingDetail && <div>Loading word…</div>}
          {selectedLexeme && !loadingDetail && (
            <div
              style={{
                padding: '0.75rem 1rem',
                borderRadius: '0.5rem',
                border: '1px solid #ddd',
                background: '#fafafa',
              }}
            >
              <h2 style={{ marginTop: 0 }}>{selectedLexeme.paiute}</h2>
              {selectedLexeme.is_multi_sense && (
                <div style={{ fontSize: '0.85em', color: '#666' }}>
                  Multiple senses / homophones
                </div>
              )}

              <h3 style={{ marginTop: '0.75rem', fontSize: '1rem' }}>Entries</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {selectedLexeme.entries.map((e) => (
                  <li key={e.id} style={{ marginBottom: '0.4rem' }}>
                    <div>{e.english}</div>
                    <div style={{ fontSize: '0.8em', color: '#555' }}>
                      L{e.lesson_id} · #{e.sort_order}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!selectedLexeme && !loadingDetail && (
            <div style={{ color: '#666' }}>Select a word to see details.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LexemeBrowser;
