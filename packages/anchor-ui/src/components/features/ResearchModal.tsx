
import React, { useState } from 'react';
import { api } from '../../services/api';
import { GlassPanel } from '../ui/GlassPanel';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

interface ResearchModalProps {
    onClose: () => void;
}

export const ResearchModal: React.FC<ResearchModalProps> = ({ onClose }) => {
    const [tab, setTab] = useState<'search' | 'direct'>('search');
    const [webQuery, setWebQuery] = useState('');
    const [results, setResults] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    const handleWebSearch = async () => {
        if (!webQuery.trim()) return;
        setLoading(true);
        try {
            const data = await api.research(webQuery);
            setResults(Array.isArray(data) ? data : []);
        } catch { alert('Search Failed'); }
        finally { setLoading(false); }
    };

    const handleSave = async (url: string) => {
        try {
            const res = await api.scrape(url, 'article');
            if (res.success) alert("Saved!"); else alert("Error: " + (res.error || "Unknown error"));
        } catch (e: any) { alert(e.message); }
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100,
            display: 'flex', justifyContent: 'center', alignItems: 'center'
        }}>
            <GlassPanel className="glass-card" style={{ width: '600px', height: '600px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <h3>Research Station</h3>
                    <Button variant="icon" aria-label="Close modal" onClick={onClose} style={{ fontSize: '1.2rem', color: 'white' }}>✕</Button>
                </div>
                <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-subtle)' }}>
                    <Button variant="ghost" onClick={() => setTab('search')} style={{ borderBottom: tab === 'search' ? '2px solid var(--accent-primary)' : 'none', borderRadius: 0, color: tab === 'search' ? 'var(--accent-primary)' : 'var(--text-primary)' }}>Web Search</Button>
                    <Button variant="ghost" onClick={() => setTab('direct')} style={{ borderBottom: tab === 'direct' ? '2px solid var(--accent-primary)' : 'none', borderRadius: 0, color: tab === 'direct' ? 'var(--accent-primary)' : 'var(--text-primary)' }}>Direct URL</Button>
                </div>

                {tab === 'search' && (
                    <>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <Input value={webQuery} onChange={e => setWebQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleWebSearch()} placeholder="Query..." />
                            <Button onClick={handleWebSearch} disabled={loading}>{loading ? '...' : 'Go'}</Button>
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {results.map((r, i) => (
                                <div key={i} style={{ padding: '0.8rem', background: '#222', borderRadius: '4px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <a href={r.link} target="_blank" rel="noopener noreferrer" style={{ color: '#8b5cf6', fontWeight: 'bold' }}>{r.title}</a>
                                        <Button variant="ghost" aria-label="Save result" onClick={() => handleSave(r.link)} style={{ fontSize: '0.7rem' }}>💾</Button>
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: '#aaa' }}>{r.snippet}</div>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {tab === 'direct' && (
                    <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <Input id="direct-url" placeholder="https://..." />
                        <Button onClick={() => {
                            const val = (document.getElementById('direct-url') as HTMLInputElement).value;
                            if (val) handleSave(val);
                        }}>Scrape & Save</Button>
                    </div>
                )}
            </GlassPanel>
        </div>
    );
};
