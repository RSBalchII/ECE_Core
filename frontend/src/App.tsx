
import { useState, useEffect } from 'react';
import './index.css';

// Simple Router (Single File for now for speed)
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
    </div>
  </div>
);

const SearchPage = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'cards' | 'raw'>('cards');

  // Feature 8/9/10 State
  const [tokenBudget, setTokenBudget] = useState(2048);
  const [activeMode, setActiveMode] = useState(false);
  const [sovereignBias, setSovereignBias] = useState(true);
  const [metadata, setMetadata] = useState<any>(null); // { tokenCount, filledPercent, atomCount }
  const [scope, setScope] = useState<'all' | 'code' | 'docs'>('all'); // <--- NEW SCOPE STATE

  // Feature 7 State
  const [backupStatus, setBackupStatus] = useState('');

  // Debounce Logic for Live Mode
  // Sync query to delay search
  useEffect(() => {
    if (!activeMode) return;
    const timer = setTimeout(() => {
      if (query.trim()) handleSearch();
    }, 500); // 500ms debounce
    return () => clearTimeout(timer);
  }, [query, activeMode, tokenBudget, sovereignBias]);

  const handleBackup = async () => {
    setBackupStatus('Backing up...');
    try {
      const res = await fetch('/v1/backup', { method: 'POST' });
      const data = await res.json();
      setBackupStatus(`Backup Saved: ${data.filename}`);
      setTimeout(() => setBackupStatus(''), 3000);
    } catch (e) {
      setBackupStatus('Backup Failed');
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
          query: scope === 'all' ? query : `${query} ${scope === 'code' ? '#code' : '#doc'}`, // <--- INJECT TAGS
          // buckets: ['notebook'], // Removed to allow global search (inbox, journals, etc.)
          max_chars: tokenBudget * 4, // Approx chars
          token_budget: tokenBudget, // For backend slicer if supported
          provenance: sovereignBias ? 'sovereign' : 'all'
        })
      });

      const data = await res.json();

      if (data.results) {
        setResults(data.results);
        setContext(data.context || '');
        setMetadata(data.metadata); // Capture metadata
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
    <div className="glass-panel" style={{ margin: '2rem', padding: '2rem', height: 'calc(100% - 4rem)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Memory Search</h2>

        {/* Helper Controls */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {/* Backup Button (Feature 7) */}
          <button className="btn-primary" onClick={handleBackup} style={{ fontSize: '0.8rem', padding: '0.4rem' }}>
            💾 {backupStatus || 'Backup'}
          </button>

          {/* Dream Button (Restored) */}
          <button
            className="btn-primary"
            style={{ background: 'rgba(100, 108, 255, 0.1)', border: '1px solid var(--accent-primary)', fontSize: '0.8rem', padding: '0.4rem' }}
            onClick={async () => {
              const btn = document.activeElement as HTMLButtonElement;
              if (btn) btn.disabled = true;
              try {
                const res = await fetch('/v1/dream', { method: 'POST' });
                const data = await res.json();
                alert(`Dream Cycle Complete:\nAnalyzed: ${data.analyzed}\nUpdated: ${data.updated}`);
              } catch (e) {
                alert('Dream Failed');
                console.error(e);
              } finally {
                if (btn) btn.disabled = false;
              }
            }}
          >
            🌙 Dream
          </button>

          {/* View Mode */}
          <button className="btn-primary" style={{ background: 'transparent', border: '1px solid var(--border-subtle)', fontSize: '0.8rem', padding: '0.4rem' }} onClick={() => setViewMode(viewMode === 'cards' ? 'raw' : 'cards')}>
            {viewMode === 'cards' ? 'Raw' : 'Cards'}
          </button>
        </div>
      </div>

      {/* RAG IDE Controls (Features 8 & 9 & 10) */}
      <div className="glass-panel" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', background: 'var(--bg-secondary)' }}>

        {/* Scope Filters (New UI) */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
          {['all', 'code', 'docs'].map(s => (
            <button
              key={s}
              className="btn-primary"
              style={{
                fontSize: '0.8rem',
                padding: '0.3rem 0.8rem',
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

        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          {/* Active Mode Toggle */}
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={activeMode} onChange={(e) => setActiveMode(e.target.checked)} />
            <span style={{ fontSize: '0.9rem', fontWeight: 'bold', color: activeMode ? 'var(--accent-primary)' : 'var(--text-dim)' }}>
              ⚡ Live Search
            </span>
          </label>

          {/* Sovereign Bias Toggle */}
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={sovereignBias} onChange={(e) => setSovereignBias(e.target.checked)} />
            <span style={{ fontSize: '0.9rem', color: sovereignBias ? '#FFD700' : 'var(--text-dim)' }}>
              👑 Sovereign Bias
            </span>
          </label>

          {/* Budget Slider */}
          <div style={{ flex: 1, display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>Budget: {tokenBudget} tokens</span>
            <input
              type="range"
              min="512"
              max="131072"
              step="512"
              value={tokenBudget}
              onChange={(e) => setTokenBudget(parseInt(e.target.value))}
              style={{ flex: 1 }}
            />
          </div>
        </div>

        {/* Context Visualization Bar */}
        <div style={{ width: '100%', height: '8px', background: 'var(--bg-tertiary)', borderRadius: '4px', overflow: 'hidden', position: 'relative' }}>
          <div style={{
            width: `${metadata?.filledPercent || 0}%`,
            height: '100%',
            background: 'linear-gradient(90deg, var(--accent-primary), #a855f7)',
            transition: 'width 0.3s ease'
          }} />
        </div>
        {metadata && (
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            <span>Used: {metadata.tokenCount || 0} tokens | {metadata.charCount || 0} chars ({(metadata.filledPercent || 0).toFixed(1)}%)</span>
            <span>Atoms: {metadata.atomCount || 0}</span>
          </div>
        )}
      </div>

      {/* Query Section */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          className="input-glass"
          placeholder="Ask your memories..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
        />
        <button className="btn-primary" onClick={handleSearch} disabled={loading}>
          Search
        </button>
      </div>

      {/* Results Section */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', paddingRight: '0.5rem' }}>

        {viewMode === 'raw' && (
          <div style={{ position: 'relative', height: '100%' }}>
            <button
              className="btn-primary"
              style={{ position: 'absolute', top: '1rem', right: '1rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', zIndex: 10 }}
              onClick={copyContext}
            >
              Copy All
            </button>
            <textarea
              className="input-glass"
              style={{ width: '100%', height: '100%', resize: 'none', fontFamily: 'monospace', fontSize: '0.9rem', lineHeight: '1.5' }}
              value={context}
              readOnly
              placeholder="Raw context will appear here..."
            />
          </div>
        )}

        {viewMode === 'cards' && results.map((r, idx) => (
          <div key={r.id || idx} className="card-result animate-fade-in" style={{ animationDelay: `${idx * 0.05}s` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <span className={`badge ${r.provenance === 'sovereign' ? 'badge-sovereign' : 'badge-external'}`}>
                  {r.provenance || 'EXTERNAL'}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                  {(r.score || 0).toFixed(2)}
                </span>
              </div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                {r.source}
              </span>
            </div>
            <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem', lineHeight: '1.5', maxHeight: '300px', overflowY: 'auto' }}>
              {r.content}
            </div>
          </div>
        ))}

        {results.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            No memories found. Try a different query.
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
              const delta = data.choices[0]?.delta?.content || '';
              assistantContent += delta;

              setMessages(prev => {
                const newMsgs = [...prev];
                const last = newMsgs[newMsgs.length - 1];
                if (last.role === 'assistant') {
                  last.content = assistantContent;
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
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Tokens: 0 / 4096</span>
            <textarea className="input-glass" style={{ flex: 1, resize: 'none', fontSize: '0.8rem' }} placeholder="Paste context here..." />
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
              {m.content}
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

function App() {
  const [route, setRoute] = useState(window.location.hash || '#');

  // Simple hash router listener
  window.addEventListener('hashchange', () => setRoute(window.location.hash));

  return (
    <>
      <nav style={{ padding: '1rem', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 'bold', cursor: 'pointer' }} onClick={() => window.location.hash = '#'}>SCE</span>
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.9rem' }}>
          <a onClick={() => window.location.hash = '#search'} style={{ cursor: 'pointer', color: route === '#search' ? 'white' : 'gray' }}>Search</a>
          <a onClick={() => window.location.hash = '#chat'} style={{ cursor: 'pointer', color: route === '#chat' ? 'white' : 'gray' }}>Chat</a>
        </div>
      </nav>
      <main style={{ flex: 1, overflow: 'hidden' }}>
        {route === '#' || route === '' ? <Dashboard /> : null}
        {route === '#search' ? <SearchPage /> : null}
        {route === '#chat' ? <ChatPage /> : null}
      </main>
    </>
  );
}

export default App;
