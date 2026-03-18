import { useState, useEffect, memo, useCallback } from 'react';
import { api } from '../../services/api';
import { GlassPanel } from '../ui/GlassPanel';
import { Button } from '../ui/Button';

interface SearchColumnProps {
    id: number;
    availableBuckets: string[];
    availableTags: string[];
    onContextUpdate: (id: number, context: string) => void;
    onFullUpdate?: (id: number, fullText: string) => void;
    onRemove: (id: number) => void;
    onAddColumn: (query?: string) => void;
    initialQuery?: string;
    columnCount: number;
    globalTokenBudget?: number;
}

export const SearchColumn = memo(({
    id,
    availableBuckets,
    availableTags,
    onContextUpdate,
    onFullUpdate,
    onRemove,
    onAddColumn,
    columnCount,
    initialQuery,
    globalTokenBudget
}: SearchColumnProps) => {
    const [query, setQuery] = useState(initialQuery || '');
    const [results, setResults] = useState<any[]>([]);
    const [context, setContext] = useState('');
    const [loading, setLoading] = useState(false);
    const [viewMode, setViewMode] = useState<'cards' | 'raw'>('cards');
    const [error, setError] = useState<string | null>(null); // New error state

    // Feature State
    const [tokenBudget, setTokenBudget] = useState(globalTokenBudget || 2048);

    // Sync with global token budget setting
    useEffect(() => {
        if (globalTokenBudget !== undefined && globalTokenBudget !== tokenBudget) {
            setTokenBudget(globalTokenBudget);
        }
    }, [globalTokenBudget]);

    // Listen for settings changes via custom event
    useEffect(() => {
        const handleSettingsChange = (event: CustomEvent<{ tokenBudget?: number }>) => {
            if (event.detail?.tokenBudget) {
                setTokenBudget(event.detail.tokenBudget);
            }
        };

        window.addEventListener('settings-changed', handleSettingsChange as EventListener);
        return () => window.removeEventListener('settings-changed', handleSettingsChange as EventListener);
    }, []);
    const [activeMode, setActiveMode] = useState(false);
    const [sovereignBias, setSovereignBias] = useState(true);
    const [metadata, setMetadata] = useState<any>(null);
    const [activeBuckets, setActiveBuckets] = useState<string[]>([]);
    const [activeTags, setActiveTags] = useState<string[]>([]);
    const [autoSplit, setAutoSplit] = useState(false);
    const [includeCode, setIncludeCode] = useState(true);
    const [showTags, setShowTags] = useState(false); // Tag Drawer Toggle
    const [chronologicalOrder, setChronologicalOrder] = useState(true); // Toggle time ordering

    // Backup Restore State
    const [backups, setBackups] = useState<Array<{ filename: string; valid: boolean; error?: string; sizeFormatted?: string }>>([]);
    const [showBackups, setShowBackups] = useState(false);
    const [restoreLoading, setRestoreLoading] = useState(false);
    const [restoreStatus, setRestoreStatus] = useState<string | null>(null);
    const [pendingRestore, setPendingRestore] = useState<string | null>(null);

    // Local Faceted Tags State
    const [localTags, setLocalTags] = useState<string[]>(availableTags);

    // Fetch tags when activeBuckets changes
    useEffect(() => {
        const fetchFacetedTags = async () => {
            try {
                // If no buckets selected, fall back to global availableTags (or fetch all)
                if (activeBuckets.length === 0) {
                    setLocalTags(availableTags);
                    return;
                }
                const tags = await api.getTags(activeBuckets);
                setLocalTags(Array.isArray(tags) ? tags : []);
            } catch (e) {
                console.error("Failed to fetch faceted tags", e);
            }
        };
        fetchFacetedTags();
    }, [activeBuckets, availableTags]);

    // Cleanup: Filter out Hex Codes
    const displayTags = localTags.filter(t => !/^#[0-9A-Fa-f]{6}$/.test(t) && !/^[0-9A-Fa-f]{6}$/.test(t));

    // Sync context to parent
    useEffect(() => {
        onContextUpdate(id, context);
    }, [context, id, onContextUpdate]);

    // Live Mode Debounce
    useEffect(() => {
        if (!activeMode) return;
        const timer = setTimeout(() => {
            if (query.trim()) {
                // Create a new array reference to force update
                setResults([]);
                handleSearch();
            }
        }, 500);
        return () => clearTimeout(timer);
    }, [query, activeMode, tokenBudget, sovereignBias, activeBuckets, activeTags, includeCode]);

    const handleQuarantine = async (atomId: string) => {
        if (!confirm('Quarantine this atom? It will be tagged #manually_quarantined.')) return;

        // Create a new array to force re-render
        setResults(prev => prev.filter(r => r.id !== atomId));
        setMetadata((prev: any) => prev ? ({ ...prev, atomCount: prev.atomCount - 1 }) : null);

        try {
            await api.quarantineAtom(atomId);
        } catch (e) {
            console.error('Quarantine failed', e);
            alert('Failed to quarantine atom server-side.');
        }
    };

    const handleSearch = useCallback(async () => {
        if (!query.trim()) return;

        setLoading(true);
        setError(null); // Clear previous errors
        // Force clear results with a new array reference to ensure UI update
        setResults([]);
        console.log(`[SearchColumn-${id}] Searching: "${query}" | Budget: ${tokenBudget}`);

        try {
            const data = await api.search({
                query: query,
                max_chars: tokenBudget * 4,
                token_budget: tokenBudget,
                provenance: sovereignBias ? 'internal' : 'all',
                buckets: activeBuckets,
                tags: activeTags,
                include_code: includeCode
            });

            if (data.results) {
                // Sort results based on toggle: chronological (causal) or relevance (associative)
                const sortedResults = data.results.sort((a: any, b: any) => {
                    if (chronologicalOrder) {
                        // Chronological: oldest first (causal narrative: Code v1 → Error → Code v2)
                        return (a.timestamp || 0) - (b.timestamp || 0);
                    } else {
                        // Relevance: highest score first (associative discovery)
                        return (b.score || 0) - (a.score || 0);
                    }
                });

                // [Consistency] Re-generate Context String to match Agent's view (~500 chars/item, ~8000 chars total)
                let currentLength = 0;
                // Dynamic Context Limit based on user slider (approx 4-6 chars per token)
                // Reduced from *8 to *4.5 to align closer with actual token expectations
                const MAX_CONTEXT_CHARS = Math.max(8192, tokenBudget * 4.5);
                const formattedContextEntries = sortedResults.map((r: any) => {
                    if (currentLength >= MAX_CONTEXT_CHARS) return null;
                    // Dynamic snippet size: Allow up to 40% of the budget per item to fill the space
                    const maxSnippetChars = Math.max(2000, Math.floor(MAX_CONTEXT_CHARS * 0.4));
                    const contentSnippet = (r.content || '').substring(0, maxSnippetChars);
                    const dateStr = r.timestamp ? new Date(r.timestamp).toISOString() : 'unknown';
                    const entry = `- [${dateStr}] ${contentSnippet}...`;
                    if (currentLength + entry.length > MAX_CONTEXT_CHARS) return null;
                    currentLength += entry.length;
                    return entry;
                }).filter(Boolean);

                const newContextString = formattedContextEntries.join('\n');

                // Create a new array with unique identifiers to force re-render
                const updatedResults = sortedResults.map((result: any, index: number) => ({
                    ...result,
                    // Add a unique key that changes with each search to force re-render
                    _searchId: `${result.id || index}_${Date.now()}_${Math.random()}`
                }));

                setResults(updatedResults);
                setContext(newContextString); // Use our consistent context string
                setMetadata(data.metadata);

                // Explicitly sync to parent to ensure global Copy button works immediately
                onContextUpdate(id, newContextString);

                if (onFullUpdate) {
                    const fullText = (updatedResults || []).map((r: any) => `[${r.provenance}] ${r.source}:\n${r.content}`).join('\n\n');
                    onFullUpdate(id, fullText);
                }

                if (autoSplit && data.split_queries && data.split_queries.length > 0) {
                    data.split_queries.forEach((q: string) => {
                        setTimeout(() => onAddColumn(q), 100);
                    });
                }

                if (updatedResults.length === 0) {
                    setContext('No results found.');
                }
            } else {
                // Create a new empty array to force update
                setResults([]);
                setContext('No results found.');
                setMetadata(null);
            }
        } catch (e: any) {
            console.error(e);
            setResults([]);
            setError(e.message || 'Unknown error occurred');
            setContext(`Error searching memories: ${e.message}`);
            setMetadata(null);
        } finally {
            setLoading(false);
        }
    }, [query, tokenBudget, sovereignBias, activeBuckets, activeTags, autoSplit, includeCode, onAddColumn, onFullUpdate, id]);

    const copyContext = async () => {
        try {
            await navigator.clipboard.writeText(context);
            alert(`Context copied! (${context.length} chars)`);
        } catch (err) {
            console.error('Failed to copy keys: ', err);
            alert('Failed to copy to clipboard. Ensure window is focused.');
        }
    };

    // Backup Restore Functions
    const fetchBackups = async () => {
        try {
            const data = await api.get('/v1/backups');
            console.log('[Backup] Fetched backups:', data);
            setBackups(Array.isArray(data) ? data : []);
            setShowBackups(true);
        } catch (e: any) {
            console.error('[Backup] Fetch failed:', e);
            alert(`Failed to fetch backups: ${e.message}`);
        }
    };

    const handleRestore = async (filename: string) => {
        // Set pending state to show inline confirmation
        setPendingRestore(filename);
    };

    const confirmRestore = async () => {
        if (!pendingRestore) return;

        console.log('[Phoenix] User confirmed, starting restore for:', pendingRestore);
        setRestoreLoading(true);
        setRestoreStatus('🔄 Starting Phoenix Protocol restore...');

        try {
            console.log('[Phoenix] Sending restore request for:', pendingRestore);
            const result = await api.post('/v1/backup/restore', { filename: pendingRestore });
            console.log('[Phoenix] Restore result:', result);

            if (result.success) {
                const stats = result.stats;
                setRestoreStatus(`✅ Restore complete!\n\n📊 Stats:\n• Atoms: ${stats.memory_count?.toLocaleString()}\n• Sources: ${stats.source_count?.toLocaleString()}\n• Engrams: ${stats.engram_count?.toLocaleString()}\n⚡ Speed: ${result.atomsPerSec || 0} atoms/second\n⏱️ Time: ${result.totalTime || 0}s`);

                // Clear search results after restore
                setResults([]);
                setContext('');
                setMetadata(null);
            } else {
                setRestoreStatus(`❌ Restore failed: ${result.error}`);
            }
        } catch (e: any) {
            console.error('[Phoenix] Restore failed:', e);
            setRestoreStatus(`❌ Restore failed: ${e.message}`);
        } finally {
            setRestoreLoading(false);
            setPendingRestore(null);
        }
    };

    const cancelRestore = () => {
        setPendingRestore(null);
    };

    const clearRestoreStatus = () => {
        setRestoreStatus(null);
        setShowBackups(false);
    };

    return (
        <GlassPanel key={`search-column-${id}`} className="search-column-glass" style={{ width: columnCount === 1 ? '100%' : 'auto', flex: '1 1 0%', minWidth: 0, padding: columnCount >= 4 ? '10px' : '20px', gap: columnCount >= 4 ? '10px' : '20px', background: 'transparent', overflow: 'hidden', border: 'none', boxShadow: 'none' }}>

            {/* Sidebar / Controls Area */}
            <div className="search-sidebar" style={{ display: 'flex', flexDirection: 'column', gap: '20px', overflowY: 'auto', paddingRight: '10px' }}>

                {/* Header / Remove Column */}
                {columnCount > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '-10px' }}>
                        <Button variant="ghost" onClick={() => onRemove(id)} style={{ color: '#ef4444', fontSize: '0.8rem', padding: '4px 8px' }}>✕ Close Tab</Button>
                    </div>
                )}

                {/* Buckets */}
                <div>
                    <label style={{ display: 'block', marginBottom: '10px', fontSize: '0.9rem', color: '#94a3b8' }}>📦 Context Buckets</label>
                    <div className="bucket-container" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {availableBuckets.filter(b => !/^\d{4}$/.test(b)).map(bucket => {
                            const isActive = activeBuckets.includes(bucket);
                            return (
                                <div
                                    key={`bucket-${id}-${bucket}`}
                                    className={`bucket-chip ${isActive ? 'active' : ''}`}
                                    onClick={() => {
                                        setActiveBuckets(prev => prev.includes(bucket) ? prev.filter(b => b !== bucket) : [...prev, bucket]);
                                    }}
                                >
                                    {(bucket || '').toLowerCase()}
                                </div>
                            );
                        })}
                        <Button onClick={() => alert('New bucket creation proxy via Chat/API')} style={{ padding: '2px 8px', fontSize: '0.9rem', borderRadius: '16px' }}>+</Button>
                    </div>
                </div>

                {/* Tags Drawer */}
                <div>
                    <div
                        style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontSize: '0.9rem', color: '#94a3b8', cursor: 'pointer' }}
                        onClick={() => setShowTags(!showTags)}
                    >
                        <label style={{ cursor: 'pointer' }}>🏷️ Semantic Tags ({activeTags.length} active)</label>
                        <span>{showTags ? '▲' : '▼'}</span>
                    </div>
                    {showTags && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '10px', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                            {displayTags.length === 0 && <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>No tags available</span>}
                            {displayTags.map(t => (
                                <div
                                    key={`tag-${id}-${t}`}
                                    className={`bucket-chip ${activeTags.includes(t) ? 'active' : ''}`}
                                    onClick={() => setActiveTags(prev => prev.includes(t) ? prev.filter(tag => tag !== t) : [...prev, t])}
                                >
                                    #{t}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Search Input */}
                <div>
                    <label htmlFor={`search-input-${id}`} style={{ display: 'block', marginBottom: '10px', fontSize: '0.9rem', color: '#94a3b8' }}>🔎 Search Memory</label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <textarea
                            id={`search-input-${id}`}
                            name="searchQuery"
                            className="input-glass"
                            placeholder="Type keyword or natural language prompt..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => {
                                // Allow Shift+Enter for newlines, Enter to search
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSearch();
                                }
                            }}
                            style={{
                                minHeight: '80px',
                                resize: 'vertical',
                                padding: '12px',
                                fontFamily: 'inherit'
                            }}
                        />
                        <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                            <Button
                                variant="primary"
                                onClick={handleSearch}
                                disabled={loading}
                                style={{ flex: 1, padding: '12px 24px' }}
                            >
                                {loading ? '⏳ Searching...' : '🔍 Fetch Context'}
                            </Button>
                            <Button
                                variant="secondary"
                                onClick={() => setChronologicalOrder(!chronologicalOrder)}
                                disabled={loading}
                                title={chronologicalOrder
                                    ? 'Currently: Chronological (causal narrative). Click to switch to Relevance (associative discovery).'
                                    : 'Currently: Relevance (associative discovery). Click to switch to Chronological (causal narrative).'
                                }
                                style={{
                                    padding: '12px 16px',
                                    background: chronologicalOrder ? '#059669' : '#7c3aed',
                                    color: '#fff',
                                    border: '1px solid #475569',
                                    minWidth: '140px'
                                }}
                            >
                                {chronologicalOrder ? '📅 Chronological' : '🎯 Relevance'}
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Slider Group & Advanced Toggles */}
                <div className="slider-group glass-card" style={{ padding: '15px', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <label htmlFor={`volume-slider-${id}`} style={{ marginBottom: '10px', display: 'block', color: '#94a3b8', fontSize: '0.9rem' }}>
                        Volume: <span>{tokenBudget * 4}</span> chars (≈<span>{tokenBudget}</span> tokens)
                    </label>
                    <input
                        id={`volume-slider-${id}`}
                        name="tokenBudget"
                        type="range"
                        min="512" max="131072" step="512"
                        value={tokenBudget}
                        onChange={(e) => setTokenBudget(parseInt(e.target.value))}
                        style={{ width: '100%', marginBottom: '15px' }}
                        aria-label="Token budget slider"
                    />

                    {/* Usage Bar equivalent */}
                    <div style={{ width: '100%', height: '4px', background: '#0f172a', borderRadius: '2px', overflow: 'hidden', marginBottom: '15px' }} role="progressbar" aria-valuenow={metadata?.filledPercent || 0} aria-valuemin={0} aria-valuemax={100}>
                        <div style={{
                            width: `${metadata?.filledPercent || 0}%`, height: '100%',
                            background: 'var(--accent-primary)',
                            transition: 'width 0.3s ease'
                        }} />
                    </div>

                    <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', color: '#94a3b8', fontSize: '0.85rem' }} role="group" aria-label="Search options">
                        <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <input
                                type="checkbox"
                                id={`live-mode-${id}`}
                                name="activeMode"
                                checked={activeMode}
                                onChange={(e) => setActiveMode(e.target.checked)}
                            />
                            <span>Live</span>
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <input
                                type="checkbox"
                                id={`sov-bias-${id}`}
                                name="sovereignBias"
                                checked={sovereignBias}
                                onChange={(e) => setSovereignBias(e.target.checked)}
                            />
                            <span>Sov Bias</span>
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <input
                                type="checkbox"
                                id={`auto-split-${id}`}
                                name="autoSplit"
                                checked={autoSplit}
                                onChange={(e) => setAutoSplit(e.target.checked)}
                            />
                            <span>Split</span>
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <input
                                type="checkbox"
                                id={`include-code-${id}`}
                                name="includeCode"
                                checked={includeCode}
                                onChange={(e) => setIncludeCode(e.target.checked)}
                            />
                            <span>Code</span>
                        </label>
                    </div>
                </div>

                {/* Utility Buttons */}
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <Button variant="primary" onClick={() => setViewMode(viewMode === 'cards' ? 'raw' : 'cards')} style={{ flex: 1, background: '#334155', color: '#fff' }}>
                        {viewMode === 'cards' ? '📄 View Raw Text' : '🃏 View Cards'}
                    </Button>
                    <Button variant="primary" onClick={copyContext} style={{ flex: 1, background: '#334155', color: '#fff' }}>
                        📋 Copy Context
                    </Button>
                    <Button
                        variant="primary"
                        onClick={fetchBackups}
                        style={{ flex: 1, background: '#7c3aed', color: '#fff' }}
                        title="Restore from backup (Phoenix Protocol)"
                    >
                        🔄 Restore Backup
                    </Button>
                </div>

                {/* Backup Restore Panel */}
                {showBackups && (
                    <div className="glass-card" style={{
                        padding: '15px',
                        marginTop: '10px'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                            <label style={{ fontSize: '0.9rem', color: '#94a3b8' }}>📦 Available Backups</label>
                            <Button variant="ghost" onClick={clearRestoreStatus} style={{ fontSize: '0.8rem', padding: '2px 8px' }}>✕</Button>
                        </div>

                        {restoreStatus && (
                            <div style={{
                                marginBottom: '10px',
                                padding: '10px',
                                borderRadius: '6px',
                                fontSize: '0.85rem',
                                whiteSpace: 'pre-wrap',
                                background: restoreStatus.includes('✅') ? 'rgba(34, 197, 94, 0.1)' :
                                    restoreStatus.includes('❌') ? 'rgba(239, 68, 68, 0.1)' :
                                        'rgba(124, 58, 237, 0.1)',
                                border: `1px solid ${restoreStatus.includes('✅') ? '#22c55e' :
                                    restoreStatus.includes('❌') ? '#ef4444' :
                                        '#7c3aed'}`,
                                color: restoreStatus.includes('✅') ? '#22c55e' :
                                    restoreStatus.includes('❌') ? '#ef4444' :
                                        '#a78bfa'
                            }}>
                                {restoreStatus}
                            </div>
                        )}

                        {restoreLoading && (
                            <div style={{ textAlign: 'center', padding: '10px', color: '#94a3b8' }}>
                                ⏳ Processing...
                            </div>
                        )}

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                            {backups.length === 0 ? (
                                <div style={{ fontSize: '0.85rem', color: '#94a3b8', textAlign: 'center', padding: '10px' }}>
                                    No backups found
                                </div>
                            ) : (
                                backups.map((backup) => {
                                    const isPending = pendingRestore === backup.filename;

                                    return (
                                        <div
                                            key={backup.filename}
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                padding: '8px 12px',
                                                background: 'var(--bg-primary)',
                                                borderRadius: '6px',
                                                border: `1px solid ${backup.valid ? '#22c55e' : '#ef4444'}`
                                            }}
                                        >
                                            <div style={{ flex: 1, fontSize: '0.85rem', color: '#94a3b8', marginRight: '10px' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                                    <span style={{ color: backup.valid ? '#a78bfa' : '#f87171', wordBreak: 'break-all', fontWeight: 'bold' }}>
                                                        {backup.filename}
                                                    </span>
                                                    {backup.sizeFormatted && (
                                                        <span style={{
                                                            fontSize: '0.75rem',
                                                            color: '#64748b',
                                                            padding: '2px 6px',
                                                            background: '#1e293b',
                                                            borderRadius: '4px'
                                                        }}>
                                                            {backup.sizeFormatted}
                                                        </span>
                                                    )}
                                                </div>
                                                {!backup.valid && (
                                                    <div style={{ fontSize: '0.75rem', color: '#ef4444', marginTop: '2px' }}>
                                                        ⚠️ {backup.error}
                                                    </div>
                                                )}
                                                {backup.valid && (backup as any).note && (
                                                    <div style={{ fontSize: '0.7rem', color: '#f59e0b', marginTop: '2px' }}>
                                                        ℹ️ {(backup as any).note}
                                                    </div>
                                                )}
                                                {isPending && (
                                                    <div style={{ fontSize: '0.75rem', color: '#f59e0b', marginTop: '4px', padding: '8px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '4px' }}>
                                                        ⚠️ Confirm restore: This will overwrite all data!
                                                    </div>
                                                )}
                                            </div>
                                            <div style={{ display: 'flex', gap: '8px' }}>
                                                {isPending ? (
                                                    <>
                                                        <button
                                                            type="button"
                                                            onClick={(e) => {
                                                                e.preventDefault();
                                                                e.stopPropagation();
                                                                confirmRestore();
                                                            }}
                                                            style={{
                                                                fontSize: '0.75rem',
                                                                padding: '4px 12px',
                                                                background: '#22c55e',
                                                                color: '#fff',
                                                                border: 'none',
                                                                borderRadius: '6px',
                                                                cursor: 'pointer'
                                                            }}
                                                        >
                                                            ✅ Confirm
                                                        </button>
                                                        <button
                                                            type="button"
                                                            onClick={(e) => {
                                                                e.preventDefault();
                                                                e.stopPropagation();
                                                                cancelRestore();
                                                            }}
                                                            style={{
                                                                fontSize: '0.75rem',
                                                                padding: '4px 12px',
                                                                background: '#ef4444',
                                                                color: '#fff',
                                                                border: 'none',
                                                                borderRadius: '6px',
                                                                cursor: 'pointer'
                                                            }}
                                                        >
                                                            ❌ Cancel
                                                        </button>
                                                    </>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            handleRestore(backup.filename);
                                                        }}
                                                        disabled={!backup.valid || restoreLoading}
                                                        style={{
                                                            fontSize: '0.75rem',
                                                            padding: '4px 12px',
                                                            background: backup.valid && !restoreLoading ? '#7c3aed' : '#475569',
                                                            color: '#fff',
                                                            border: 'none',
                                                            borderRadius: '6px',
                                                            cursor: !backup.valid || restoreLoading ? 'not-allowed' : 'pointer',
                                                            opacity: !backup.valid || restoreLoading ? 0.5 : 1
                                                        }}
                                                        title={!backup.valid ? 'Invalid backup' : restoreLoading ? 'Restoring...' : 'Restore this backup'}
                                                    >
                                                        🔄 Restore
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>
                )}

            </div>

            {/* Main Output Area */}
            <div className="main glass-card" style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                padding: '20px',
                minHeight: '400px'
            }}>
                {loading && <div style={{ color: '#94a3b8', textAlign: 'center', padding: '20px' }}>Loading...</div>}
                {error && <div style={{ color: '#ef4444', textAlign: 'center', padding: '20px', border: '1px solid #ef4444', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)' }}>{error}</div>}

                {!loading && !error && viewMode === 'raw' && (
                    <textarea
                        style={{ flex: 1, background: '#000', color: '#a5f3fc', border: 'none', padding: '15px', fontFamily: 'monospace', resize: 'none', outline: 'none', borderRadius: '8px', width: '100%', boxSizing: 'border-box' }}
                        value={context}
                        readOnly
                        placeholder="Context results will appear here..."
                    />
                )}

                {!loading && !error && viewMode === 'cards' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', overflowY: 'auto', flex: 1 }}>
                        {results.length === 0 ? (
                            <div style={{ color: '#94a3b8', textAlign: 'center', padding: '20px' }}>Search results will appear here...</div>
                        ) : (
                            results.map((r, idx) => {
                                const isIncluded = metadata?.atomCount ? idx < metadata.atomCount : true;
                                return (
                                    <div key={`${r._searchId || r.id || idx}-${id}`} className="glass-card" style={{ opacity: isIncluded ? 1 : 0.5, borderLeft: isIncluded ? '2px solid var(--accent-primary)' : '2px solid transparent', padding: '15px', color: '#a5f3fc', fontFamily: 'var(--font-mono)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                <span style={{ fontSize: '0.7rem', padding: '4px 8px', borderRadius: '4px', background: '#334155', color: '#94a3b8', fontWeight: 'bold' }}>{r.provenance || 'EXT'}</span>
                                                {!isIncluded && <span style={{ fontSize: '0.7rem', color: '#f59e0b' }}>[Truncated]</span>}
                                            </div>
                                            <Button variant="icon" aria-label="Quarantine item" onClick={() => handleQuarantine(r.id)} style={{ color: '#ef4444', fontSize: '1.2rem', padding: '0 4px' }}>🚫</Button>
                                        </div>
                                        <div style={{ whiteSpace: 'pre-wrap', maxHeight: '300px', overflowY: 'auto' }}>{r.content}</div>
                                    </div>
                                );
                            })
                        )}
                    </div>
                )}
            </div>

        </GlassPanel>
    );
});

// Add a display name for better debugging
SearchColumn.displayName = 'SearchColumn';