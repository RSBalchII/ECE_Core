
import { useState, useEffect, useCallback, memo } from 'react';
import './index.css';
import PerformanceMonitor from './components/PerformanceMonitor';

// Simple Router
const Dashboard = () => (
  <div className="flex-col-center" style={{ height: '100%', justifyContent: 'center', alignItems: 'center', gap: '2rem' }}>
    <h1 style={{ fontSize: '3rem', background: 'linear-gradient(to right, #fff, #646cff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
      Sovereign Context Engine
    </h1>
    <div style={{ display: 'flex', gap: '1rem' }}>
      <button className="btn-primary" onClick={() => window.location.hash = '#search'}>
        Search Memories
      </button>
      <button className="btn-primary" onClick={() => window.location.hash = '#chat'}>
        Launch Chat
      </button>
      <button className="btn-primary" onClick={() => window.location.hash = '#quarantine'}>
        Infection Center
      </button>
    </div>
  </div>
);

// --- SEARCH COLUMN COMPONENT ---
interface SearchColumnProps {
  id: number;
  availableBuckets: string[];
  availableTags: string[];
  onContextUpdate: (id: number, context: string) => void;
  onFullUpdate?: (id: number, fullText: string) => void;
  onRemove: (id: number) => void;
  onAddColumn: (query?: string) => void; // Access to parent adder
  initialQuery?: string;
  isOnly: boolean;
}

const SearchColumn = memo(({ id, availableBuckets, availableTags, onContextUpdate, onFullUpdate, onRemove, onAddColumn, isOnly, initialQuery }: SearchColumnProps) => {
  const [query, setQuery] = useState(initialQuery || '');
  const [results, setResults] = useState<any[]>([]);
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'cards' | 'raw'>('cards');

  // Feature 8/9/10 State per column
  const [tokenBudget, setTokenBudget] = useState(2048);
  const [activeMode, setActiveMode] = useState(false);
  const [sovereignBias, setSovereignBias] = useState(true);
  const [metadata, setMetadata] = useState<any>(null);
  const [scope, setScope] = useState<'all' | 'code' | 'docs'>('all');

  // Sync context to parent whenever it changes
  useEffect(() => {
    onContextUpdate(id, context);
  }, [context, id, onContextUpdate]);

  // Debounce Logic for Live Mode
  useEffect(() => {
    if (!activeMode) return;
    const timer = setTimeout(() => {
      if (query.trim()) handleSearch();
    }, 500);
    return () => clearTimeout(timer);
  }, [query, activeMode, tokenBudget, sovereignBias, scope]);

  const handleQuarantine = async (atomId: string) => {
    if (!confirm('Quarantine this atom? It will be tagged #manually_quarantined.')) return;
    setResults(prev => prev.filter(r => r.id !== atomId));
    setMetadata((prev: any) => prev ? ({ ...prev, atomCount: prev.atomCount - 1 }) : null);
    try {
      await fetch(`/v1/atoms/${atomId}/quarantine`, { method: 'POST' });
    } catch (e) {
      console.error('Quarantine failed', e);
      alert('Failed to quarantine atom server-side.');
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResults([]);
    try {
      const res = await fetch('/v1/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: scope === 'all' ? query : `${query} ${scope === 'code' ? '#code' : '#doc'}`,
          max_chars: tokenBudget * 4,
          token_budget: tokenBudget,
          provenance: sovereignBias ? 'internal' : 'all'
        })
      });

      const data = await res.json();
      if (data.results) {
        setResults(data.results);
        setContext(data.context || '');
        setMetadata(data.metadata);

        // Aggregate Full Text (All results)
        if (onFullUpdate) {
          const fullText = (data.results || []).map((r: any) => `[${r.provenance}] ${r.source}:\n${r.content}`).join('\n\n');
          onFullUpdate(id, fullText);
        }

        // Auto-Spawn Columns if Split Queries detected
        if (data.split_queries && data.split_queries.length > 0) {
          // We only spawn if we haven't already? Or just do it.
          // To prevent infinite loops or clutter, maybe we check if we are already a split?
          // For now, simpler: Just spawn them. The user can close.
          data.split_queries.forEach((q: string) => {
            // Delay slightly to look nice
            setTimeout(() => onAddColumn(q), 100);
          });
        }
      } else {
        setResults([]);
        setContext('No results found.');
        setMetadata(null);
      }
    } catch (e) {
      console.error(e);
      setContext('Error searching memories.');
    } finally {
      setLoading(false);
    }
  };

  const copyContext = () => {
    navigator.clipboard.writeText(context);
  };

  return (
    <div className="glass-panel" style={{ flex: 1, padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', background: 'var(--bg-secondary)', minWidth: '300px', overflow: 'hidden' }}>

      {/* Column Header / Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {['all', 'code', 'docs'].map(s => (
            <button
              key={s}
              className="btn-primary"
              style={{
                fontSize: '0.7rem', padding: '0.2rem 0.5rem',
                background: scope === s ? 'var(--accent-primary)' : 'transparent',
                border: scope === s ? 'none' : '1px solid var(--border-subtle)',
                opacity: scope === s ? 1 : 0.7
              }}
              onClick={() => setScope(s as any)}
            >
              {s.toUpperCase()}
            </button>
          ))}
        </div>
        {!isOnly && (
          <button onClick={() => onRemove(id)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>✕</button>
        )}
      </div>

      {/* Advanced Toggles */}
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', cursor: 'pointer' }}>
          <input type="checkbox" checked={activeMode} onChange={(e) => setActiveMode(e.target.checked)} />
          <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: activeMode ? 'var(--accent-primary)' : 'var(--text-dim)' }}>Live</span>
        </label>
        <label style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', cursor: 'pointer' }}>
          <input type="checkbox" checked={sovereignBias} onChange={(e) => setSovereignBias(e.target.checked)} />
          <span style={{ fontSize: '0.8rem', color: sovereignBias ? '#FFD700' : 'var(--text-dim)' }}>Sov</span>
        </label>
        <div style={{ flex: 1, display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>{tokenBudget} tks</span>
          <input
            type="range" min="512" max="131072" step="512"
            value={tokenBudget} onChange={(e) => setTokenBudget(parseInt(e.target.value))}
            style={{ flex: 1, minWidth: '50px' }}
          />
        </div>
      </div>

      {/* Usage Bar */}
      <div style={{ width: '100%', height: '4px', background: 'var(--bg-tertiary)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{
          width: `${metadata?.filledPercent || 0}%`, height: '100%',
          background: 'linear-gradient(90deg, var(--accent-primary), #a855f7)',
          transition: 'width 0.3s ease'
        }} />
      </div>
      {metadata && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-dim)' }}>
          <span>Context: {metadata.tokenCount || 0} / {tokenBudget} tokens</span>
          <span>{metadata.atomCount || 0} atoms included</span>
        </div>
      )}

      {/* Badges */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', maxHeight: '60px', overflowY: 'auto' }}>
        {availableBuckets.filter(b => !/^\d{4}$/.test(b)).map(b => (
          <span key={b} onClick={() => setQuery(prev => prev + ` #${b}`)} style={{
            fontSize: '0.65rem', padding: '0.1rem 0.4rem', borderRadius: '8px',
            background: 'rgba(100, 108, 255, 0.2)', color: '#a5b4fc', cursor: 'pointer'
          }}>#{b}</span>
        ))}
        {availableTags.filter(t => !/^\d{4}$/.test(t)).map(t => (
          <span key={t} onClick={() => setQuery(prev => prev + ` #${t}`)} style={{
            fontSize: '0.65rem', padding: '0.1rem 0.4rem', borderRadius: '8px',
            background: 'rgba(236, 72, 153, 0.15)', color: '#f9a8d4', cursor: 'pointer'
          }}>#{t}</span>
        ))}
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          className="input-glass"
          placeholder="Query..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
          style={{ fontSize: '0.9rem' }}
        />
        <button className="btn-primary" onClick={handleSearch} disabled={loading} style={{ padding: '0.4rem' }}>
          🔍
        </button>
        <button
          className="btn-primary"
          onClick={() => setViewMode(viewMode === 'cards' ? 'raw' : 'cards')}
          style={{ padding: '0.4rem', fontSize: '0.8rem', background: viewMode === 'raw' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)' }}
          title="Toggle Raw/Cards View"
        >
          {viewMode === 'cards' ? '📄' : '🃏'}
        </button>
      </div>

      {/* Results */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.8rem', paddingRight: '0.3rem' }}>
        {viewMode === 'raw' ? (
          <div style={{ position: 'relative', height: '100%' }}>
            <button className="btn-primary" onClick={copyContext}
              style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', fontSize: '0.7rem', padding: '0.2rem 0.5rem', zIndex: 10 }}>
              Copy
            </button>
            <textarea
              className="input-glass"
              style={{ width: '100%', height: '100%', resize: 'none', fontFamily: 'monospace', fontSize: '0.95rem' }}
              value={context} readOnly placeholder="Raw context..."
            />
          </div>
        ) : (
          results.map((r, idx) => {
            const isIncluded = metadata?.atomCount ? idx < metadata.atomCount : true;
            return (
              <div key={r.id || idx} className="card-result" style={{
                padding: '0.8rem', fontSize: '0.9rem',
                opacity: isIncluded ? 1 : 0.5,
                borderLeft: isIncluded ? '2px solid var(--accent-primary)' : '2px solid transparent'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className={`badge ${r.provenance === 'sovereign' ? 'badge-sovereign' : 'badge-external'}`} style={{ fontSize: '0.7rem' }}>
                      {r.provenance || 'EXT'}
                    </span>
                    {!isIncluded && <span style={{ fontSize: '0.65rem', color: 'orange' }}>[Context Limit Reached]</span>}
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{(r.score || 0).toFixed(1)}</span>
                    <button onClick={() => handleQuarantine(r.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.9rem', padding: 0 }}>🚫</button>
                  </div>
                </div>
                <div style={{ maxHeight: '200px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>{r.content}</div>
              </div>
            );
          })
        )}
        {results.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-dim)', fontSize: '0.8rem' }}>No results</div>
        )}
      </div>

      {/* Footer / Toggle View */}
      <div style={{ display: 'flex', justifyContent: 'center', height: '10px' }}>
        {/* Footer Spacer */}
      </div>
    </div>
  );
});

// --- SEARCH PAGE CONTAINER ---
const SearchPage = () => {
  const [columns, setColumns] = useState<{ id: number; query?: string }[]>([{ id: 1 }]);
  const [columnContexts, setColumnContexts] = useState<Record<number, string>>({});
  const [columnFullTexts, setColumnFullTexts] = useState<Record<number, string>>({});

  console.log('[SearchPage] Render. Columns:', columns);

  useEffect(() => {
    console.log('[SearchPage] MOUNTED');
    return () => console.log('[SearchPage] UNMOUNTED');
  }, []);

  // Global State
  const [backupStatus, setBackupStatus] = useState('');
  const [showResearch, setShowResearch] = useState(false);
  const [availableBuckets, setAvailableBuckets] = useState<string[]>([]);
  const [availableTags, setAvailableTags] = useState<string[]>([]);

  useEffect(() => {
    Promise.all([
      fetch('/v1/buckets').then(r => r.json()).catch(() => []),
      fetch('/v1/tags').then(r => r.json()).catch(() => [])
    ]).then(([buckets, tags]) => {
      setAvailableBuckets(Array.isArray(buckets) ? buckets : []);
      setAvailableTags(Array.isArray(tags) ? tags : []);
    });
  }, []);

  const addColumn = useCallback((initialQuery?: string) => {
    setColumns(prev => {
      if (prev.length >= 8) return prev;
      const newId = (prev.length > 0 ? Math.max(...prev.map(c => c.id)) : 0) + 1;
      return [...prev, { id: newId, query: initialQuery }];
    });
  }, []);

  const removeColumn = useCallback((id: number) => {
    console.log('[SearchPage] removeColumn called for ID:', id);
    setColumns(prev => prev.filter(c => c.id !== id));
    setColumnContexts(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    setColumnFullTexts(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  const handleContextUpdate = useCallback((id: number, ctx: string) => {
    setColumnContexts(prev => ({ ...prev, [id]: ctx }));
  }, []);

  const handleFullUpdate = useCallback((id: number, full: string) => {
    setColumnFullTexts(prev => ({ ...prev, [id]: full }));
  }, []);

  const copyContextWindow = () => {
    const all = Object.values(columnContexts).filter(c => c && c.trim()).join('\n\n' + '='.repeat(40) + '\n\n');
    if (!all) return alert("No context to copy.");
    navigator.clipboard.writeText(all);
    alert("Context Window (Limited) Copied!");
  };

  const copyFullResults = () => {
    const all = Object.values(columnFullTexts).filter(c => c && c.trim()).join('\n\n' + '='.repeat(40) + '\n\n');
    if (!all) return alert("No results to copy.");
    navigator.clipboard.writeText(all);
    alert("ALL Results (Unlimited) Copied!");
  };

  const handleBackup = async () => {
    setBackupStatus('Saving...');
    try {
      const res = await fetch('/v1/backup', { method: 'POST' });
      const data = await res.json();
      setBackupStatus(`Saved: ${data.filename}`);
      setTimeout(() => setBackupStatus(''), 3000);
    } catch { setBackupStatus('Failed'); }
  };

  return (
    <div className="glass-panel search-page-container" style={{ margin: '1rem', padding: '1rem', height: 'calc(100% - 2rem)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>

      {/* GLOBAL HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Memory Command</h2>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn-primary" onClick={handleBackup} style={{ fontSize: '0.8rem', padding: '0.4rem' }}>
            💾 {backupStatus || 'Backup'}
          </button>
          <button className="btn-primary" onClick={() => setShowResearch(true)} style={{ fontSize: '0.8rem', padding: '0.4rem' }}>
            🕵️ Research
          </button>
          <button className="btn-primary" onClick={async () => {
            const res = await fetch('/v1/dream', { method: 'POST' });
            const d = await res.json();
            alert(`Dream Analyzed: ${d.analyzed}`);
          }} style={{ background: 'rgba(100, 108, 255, 0.1)', fontSize: '0.8rem', padding: '0.4rem' }}>
            🌙 Dream
          </button>

          <div style={{ width: '1px', height: '20px', background: 'var(--border-subtle)', margin: '0 0.5rem' }} />

          <button className="btn-primary" onClick={copyContextWindow} style={{ fontSize: '0.8rem', padding: '0.4rem', border: '1px solid var(--accent-primary)' }}>
            📄 Copy Limit ({columns.length})
          </button>
          <button className="btn-primary" onClick={copyFullResults} style={{ fontSize: '0.8rem', padding: '0.4rem', border: '1px solid var(--accent-primary)' }}>
            📚 Copy All (∞)
          </button>
          <button className="btn-primary" onClick={() => addColumn()} disabled={columns.length >= 8} style={{ fontSize: '1rem', padding: '0.2rem 0.8rem', background: 'var(--accent-primary)', color: 'white' }}>
            +
          </button>
        </div>
      </div>

      {/* COLUMNS CONTAINER */}
      <div className="search-grid">
        {columns.map(col => (
          <SearchColumn
            key={col.id}
            id={col.id}
            availableBuckets={availableBuckets}
            availableTags={availableTags}
            onContextUpdate={handleContextUpdate}
            onFullUpdate={handleFullUpdate}
            onRemove={removeColumn}
            onAddColumn={addColumn}
            isOnly={columns.length === 1}
            initialQuery={col.query}
          />
        ))}
      </div>

      {/* Research Modal Re-integrated */}
      {showResearch && <ResearchModal onClose={() => setShowResearch(false)} />}
    </div>
  );
};

// --- RESEARCH MODAL (Extracted) ---
const ResearchModal = ({ onClose }: { onClose: () => void }) => {
  const [tab, setTab] = useState<'search' | 'direct'>('search');
  const [webQuery, setWebQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleWebSearch = async () => {
    if (!webQuery.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/v1/research/web-search?q=${encodeURIComponent(webQuery)}`);
      const data = await res.json();
      setResults(Array.isArray(data) ? data : []);
    } catch { alert('Search Failed'); }
    finally { setLoading(false); }
  };

  const handleSave = async (url: string) => {
    try {
      const res = await fetch('/v1/research/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, category: 'article' })
      });
      if (res.ok) alert("Saved!"); else alert("Error saving.");
    } catch (e: any) { alert(e.message); }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100,
      display: 'flex', justifyContent: 'center', alignItems: 'center'
    }}>
      <div className="glass-panel" style={{ width: '600px', height: '600px', padding: '1.5rem', background: '#1a1a1a', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <h3>Research Station</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'white', fontSize: '1.2rem', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid #333' }}>
          <button onClick={() => setTab('search')} style={{ padding: '0.5rem', borderBottom: tab === 'search' ? '2px solid white' : 'none', background: 'none', color: 'white', cursor: 'pointer' }}>Web Search</button>
          <button onClick={() => setTab('direct')} style={{ padding: '0.5rem', borderBottom: tab === 'direct' ? '2px solid white' : 'none', background: 'none', color: 'white', cursor: 'pointer' }}>Direct URL</button>
        </div>

        {tab === 'search' && (
          <>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input className="input-glass" value={webQuery} onChange={e => setWebQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleWebSearch()} placeholder="Query..." />
              <button className="btn-primary" onClick={handleWebSearch} disabled={loading}>{loading ? '...' : 'Go'}</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {results.map((r, i) => (
                <div key={i} style={{ padding: '0.8rem', background: '#222', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <a href={r.link} target="_blank" style={{ color: '#8b5cf6', fontWeight: 'bold' }}>{r.title}</a>
                    <button onClick={() => handleSave(r.link)} style={{ fontSize: '0.7rem' }}>💾</button>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#aaa' }}>{r.snippet}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === 'direct' && (
          <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <input className="input-glass" id="direct-url" placeholder="https://..." />
            <button className="btn-primary" onClick={() => {
              const val = (document.getElementById('direct-url') as HTMLInputElement).value;
              if (val) handleSave(val);
            }}>Scrape Link</button>
          </div>
        )}
      </div>
    </div>
  );
};

const ChatPage = () => {
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([
    { role: 'assistant', content: 'Welcome to the Sovereign Chat. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [ragContext, setRagContext] = useState('');

  // Model Config State
  const [modelDir, setModelDir] = useState('../models');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [currentModel, setCurrentModel] = useState('');
  const [modelLoading, setModelLoading] = useState(false);

  // Scan Models
  const scanModels = async () => {
    try {
      const res = await fetch(`/v1/models?dir=${encodeURIComponent(modelDir)}`);
      if (!res.ok) throw new Error('Failed to scan');
      const models = await res.json();
      setAvailableModels(models);
      if (models.length > 0 && !selectedModel) setSelectedModel(models[0]);
    } catch (e) {
      console.error(e);
      alert('Failed to scan directory');
    }
  };

  // Load Model
  const loadModel = async () => {
    if (!selectedModel) return;
    setModelLoading(true);
    try {
      // If custom directory, we must pass it OR pass full path?
      // API /v1/inference/load accepts direct 'dir'.
      const res = await fetch('/v1/inference/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel,
          dir: modelDir
        })
      });
      const data = await res.json();
      if (res.ok) {
        setCurrentModel(selectedModel);
        alert(`Model Loaded: ${selectedModel}`);
      } else {
        throw new Error(data.error);
      }
    } catch (e: any) {
      console.error(e);
      alert(`Load Failed: ${e.message}`);
    } finally {
      setModelLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    // Initial empty assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const res = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            { role: 'system', content: 'You are a helpful assistant serving the Sovereign Context Engine.' },
            ...messages.map(m => ({ role: m.role, content: m.content })),
            { role: 'user', content: userMsg }
          ],
          stream: true
        })
      });

      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim();
            if (dataStr === '[DONE]') break;

            try {
              const data = JSON.parse(dataStr);

              // HANDLE TOOL EVENTS
              if (data.type === 'tool') {
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: `🛠️ Searching: "${data.query}" (Budget: ${data.budget})...`,
                  isTool: true
                } as any]);
                assistantContent = '';
                continue;
              }

              if (data.type === 'tool_result') {
                setRagContext(prev => prev + data.full_context + "\n\n");
                setMessages(prev => {
                  const newMsgs = [...prev];
                  // Find the last tool message and update it
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  if ((lastMsg as any).isTool) {
                    lastMsg.content += `\n✅ ${data.content}`;
                    // Optional: Store full context in expanded state?
                    // For now just append to text.
                  }
                  return newMsgs;
                });
                continue;
              }

              const delta = data.choices?.[0]?.delta?.content || '';
              assistantContent += delta;

              setMessages(prev => {
                const newMsgs = [...prev];
                const last = newMsgs[newMsgs.length - 1];
                // Ensure we are appending to an assistant message, not a tool message
                if (last.role === 'assistant' && !(last as any).isTool) {
                  last.content = assistantContent;
                } else if (delta) {
                  // New assistant message chunk after a tool output
                  newMsgs.push({ role: 'assistant', content: assistantContent });
                }
                return newMsgs;
              });
            } catch (e) {
              console.error('Error parsing SSE:', e);
            }
          }
        }
      }

    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Could not connect to inference engine.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr', height: '100%' }}>
      {/* Sidebar */}
      <div style={{ padding: '1rem', borderRight: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>

        {/* Model Config Panel */}
        <div>
          <h3>Model Config</h3>
          <div className="glass-panel" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Directory</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input className="input-glass" style={{ fontSize: '0.8rem', padding: '0.4rem' }} value={modelDir} onChange={(e) => setModelDir(e.target.value)} />
                <button className="btn-primary" style={{ padding: '0.4rem' }} onClick={scanModels}>Scan</button>
              </div>
            </div>

            {availableModels.length > 0 && (
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Select Model</label>
                <select
                  className="input-glass"
                  style={{ fontSize: '0.8rem', padding: '0.4rem' }}
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <button
                  className="btn-primary"
                  style={{ width: '100%', marginTop: '0.5rem', background: currentModel === selectedModel ? 'var(--bg-tertiary)' : 'var(--accent-primary)' }}
                  onClick={loadModel}
                  disabled={modelLoading}
                >
                  {modelLoading ? 'Loading...' : currentModel === selectedModel ? 'Active' : 'Load Model'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Context Panel */}
        <div style={{ flex: 1 }}>
          <h3>Context</h3>
          <div className="glass-panel" style={{ padding: '1rem', height: '100%', display: 'flex', flexDirection: 'column', gap: '0.5rem', minHeight: '150px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Tokens: {ragContext.length / 4} / 4096</span>
            <textarea
              className="input-glass"
              style={{ flex: 1, resize: 'none', fontSize: '0.8rem' }}
              placeholder="RAG Context will appear here..."
              value={ragContext}
              readOnly
            />
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ flex: 1, padding: '2rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.map((m, idx) => (
            <div key={idx} className={`glass-panel animate-fade-in`} style={{
              padding: '1rem',
              maxWidth: '80%',
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              background: m.role === 'user' ? 'rgba(100, 108, 255, 0.1)' : 'var(--glass-bg)',
              whiteSpace: 'pre-wrap'
            }}>
              {m.content.split(/(<search.*?>.*?<\/search>)/gs).map((part, i) => (
                part.startsWith('<search')
                  ? null // HIDE the raw tag from the bubble
                  : <span key={i}>{part}</span>
              ))}
            </div>
          ))}
          {loading && <div style={{ alignSelf: 'flex-start', color: 'var(--text-dim)', fontSize: '0.8rem', marginLeft: '1rem' }}>Thinking...</div>}
        </div>
        <div style={{ padding: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <textarea
              className="input-glass"
              rows={2}
              placeholder="Type a message..."
              style={{ resize: 'none' }}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
            />
            <button className="btn-primary" style={{ height: 'auto' }} onClick={sendMessage} disabled={loading}>Send</button>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- QUARANTINE PAGE COMPONENT ---
const QuarantinePage = () => {
  const [atoms, setAtoms] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');

  const fetchAtoms = async () => {
    setLoading(true);
    try {
      const res = await fetch('/v1/atoms/quarantined');
      const data = await res.json();
      setAtoms(Array.isArray(data) ? data : []);
    } catch {
      alert("Failed to load quarantined atoms.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAtoms();
  }, []);

  const handleRestore = async (id: string) => {
    if (!confirm('Restore this atom to the sovereign graph?')) return;
    try {
      await fetch(`/v1/atoms/${id}/restore`, { method: 'POST' });
      setAtoms(prev => prev.filter(a => a.id !== id));
      alert('Restored!');
    } catch {
      alert('Restore failed.');
    }
  };

  const startEdit = (atom: any) => {
    setEditingId(atom.id);
    setEditContent(atom.content);
  };

  const saveEdit = async () => {
    if (!editingId) return;
    try {
      await fetch(`/v1/atoms/${editingId}/content`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editContent })
      });
      setAtoms(prev => prev.map(a => a.id === editingId ? { ...a, content: editContent } : a));
      setEditingId(null);
      alert('Updated!');
    } catch {
      alert('Update failed.');
    }
  };

  return (
    <div className="glass-panel" style={{ margin: '1rem', padding: '1rem', height: 'calc(100% - 2rem)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h2>Quarantine Center</h2>
        <button className="btn-primary" onClick={fetchAtoms}>Refresh</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {atoms.length === 0 && !loading && <div style={{ padding: '2rem', textAlign: 'center', color: 'gray' }}>No quarantined atoms found.</div>}

        {atoms.map(atom => (
          <div key={atom.id} className="card-result" style={{ padding: '1rem', border: '1px solid #441111', background: 'rgba(50,10,10,0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.8rem', color: '#ff6666' }}>{new Date(atom.timestamp).toLocaleString()} | {atom.source}</span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {editingId === atom.id ? (
                  <>
                    <button className="btn-primary" onClick={saveEdit}>Save</button>
                    <button className="btn-text" onClick={() => setEditingId(null)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <button className="btn-primary" style={{ fontSize: '0.8rem' }} onClick={() => startEdit(atom)}>Edit</button>
                    <button className="btn-primary" style={{ fontSize: '0.8rem', background: '#225522' }} onClick={() => handleRestore(atom.id)}>Restore</button>
                  </>
                )}
              </div>
            </div>

            {editingId === atom.id ? (
              <textarea
                className="input-glass"
                style={{ width: '100%', minHeight: '150px' }}
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
              />
            ) : (
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: '#dddddd' }}>{atom.content}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

function App() {
  const [route, setRoute] = useState(window.location.hash || '#');

  // Simple hash router listener
  useEffect(() => {
    const handler = () => setRoute(window.location.hash);
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  // Electron Detection
  const [isElectron, setIsElectron] = useState(false);

  useEffect(() => {
    // @ts-ignore
    if (window.electronAPI?.isElectron()) setIsElectron(true);
  }, []);

  return (
    <>
      {isElectron && <TitleBar />}
      <nav style={{ padding: '1rem', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: isElectron ? '30px' : '0' }}>
        <span style={{ fontWeight: 'bold', cursor: 'pointer' }} onClick={() => window.location.hash = '#'}>SCE</span>
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.9rem' }}>
          <a onClick={() => window.location.hash = '#search'} style={{ cursor: 'pointer', color: route === '#search' ? 'white' : 'gray' }}>Search</a>
          <a onClick={() => window.location.hash = '#chat'} style={{ cursor: 'pointer', color: route === '#chat' ? 'white' : 'gray' }}>Chat</a>
          <a onClick={() => window.location.hash = '#quarantine'} style={{ cursor: 'pointer', color: route === '#quarantine' ? '#ff6666' : 'gray' }}>Quarantine</a>
        </div>
      </nav>
      <main style={{ flex: 1, overflow: 'hidden' }}>
        {route === '#' || route === '' ? <Dashboard /> : null}
        {route === '#search' ? <SearchPage /> : null}
        {route === '#chat' ? <ChatPage /> : null}
        {route === '#quarantine' ? <QuarantinePage /> : null}
      </main>
      <PerformanceMonitor />
    </>
  );
}

const TitleBar = () => (
  <div style={{
    position: 'fixed', top: 0, left: 0, right: 0, height: '32px',
    background: 'rgba(0,0,0,0.8)', borderBottom: '1px solid var(--border-subtle)',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '0 10px', zIndex: 9999,
    // @ts-ignore - Electron drag region
    WebkitAppRegion: 'drag', userSelect: 'none'
  }}>
    <span style={{ fontSize: '0.8rem', color: '#888', fontWeight: 'bold' }}>ECE Desktop</span>
    <div style={{ display: 'flex', gap: '8px', WebkitAppRegion: 'no-drag' } as any}>
      <button onClick={() => (window as any).electronAPI.minimize()} style={{ background: 'none', border: 'none', color: '#ccc', cursor: 'pointer' }}>─</button>
      <button onClick={() => (window as any).electronAPI.maximize()} style={{ background: 'none', border: 'none', color: '#ccc', cursor: 'pointer' }}>□</button>
      <button onClick={() => (window as any).electronAPI.close()} style={{ background: 'none', border: 'none', color: '#ff5555', cursor: 'pointer' }}>✕</button>
    </div>
  </div>
);

export default App;
