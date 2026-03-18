import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { GlassPanel } from '../ui/GlassPanel';
import { Button } from '../ui/Button';

interface GitCommandsModalProps {
    onClose: () => void;
}

interface GitCommandResult {
    command: string;
    output: string;
    error?: string;
    success: boolean;
}

export const GitCommandsModal: React.FC<GitCommandsModalProps> = ({ onClose }) => {
    const [selectedCommand, setSelectedCommand] = useState<string>('status');
    const [workingDir, setWorkingDir] = useState('');
    const [result, setResult] = useState<GitCommandResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [availableRepos, setAvailableRepos] = useState<string[]>([]);

    useEffect(() => {
        // Load available repos from backend
        api.getGitRepos()
            .then(repos => {
                if (Array.isArray(repos)) {
                    setAvailableRepos(repos);
                    if (repos.length > 0) {
                        setWorkingDir(repos[0]);
                    }
                }
            })
            .catch(err => console.error("Failed to load git repos", err));
    }, []);

    const handleRunCommand = async () => {
        const commandToRun = selectedCommand;
        if (!commandToRun.trim() || !workingDir) return;

        setLoading(true);
        setResult(null);

        try {
            const data = await api.runGitCommand(commandToRun, workingDir);
            setResult(data);
        } catch (e: any) {
            setResult({
                command: commandToRun,
                output: '',
                error: e.message,
                success: false
            });
        } finally {
            setLoading(false);
        }
    };

    const predefinedCommands = [
        { value: 'status', label: '📊 git status', description: 'Show working tree status' },
        { value: 'log --oneline -20', label: '📜 git log (recent)', description: 'Last 20 commits' },
        { value: 'log --graph --oneline -15', label: '🌲 git log (graph)', description: 'Visual commit graph' },
        { value: 'diff', label: '🔀 git diff', description: 'Unstaged changes' },
        { value: 'diff --cached', label: '🔀 git diff --cached', description: 'Staged changes' },
        { value: 'branch -a', label: '🌿 git branch', description: 'List all branches' },
        { value: 'remote -v', label: '🔗 git remote', description: 'Remote repositories' }
    ];

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100,
            display: 'flex', justifyContent: 'center', alignItems: 'center'
        }}>
            <GlassPanel className="glass-card" style={{
                width: '700px',
                maxHeight: '80vh',
                padding: '1.5rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
                overflow: 'hidden'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0 }}>Git Commands</h3>
                    <Button variant="icon" aria-label="Close modal" onClick={onClose} style={{ fontSize: '1.2rem', color: 'white' }}>✕</Button>
                </div>

                {/* Working Directory Selection */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Repository</label>
                    <select
                        value={workingDir}
                        onChange={e => setWorkingDir(e.target.value)}
                        style={{ flex: 1, padding: '0.5rem', background: '#222', color: 'white', border: '1px solid #444', borderRadius: '4px' }}
                    >
                        {availableRepos.length === 0 && <option value="">No repos available...</option>}
                        {availableRepos.map(repo => (
                            <option key={repo} value={repo}>{repo}</option>
                        ))}
                    </select>
                </div>

                {/* Command Selection */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Command</label>
                    <select
                        value={selectedCommand}
                        onChange={e => setSelectedCommand(e.target.value)}
                        style={{ padding: '0.5rem', background: '#222', color: 'white', border: '1px solid #444', borderRadius: '4px' }}
                    >
                        {predefinedCommands.map(cmd => (
                            <option key={cmd.value} value={cmd.value}>{cmd.label}</option>
                        ))}
                    </select>
                </div>

                {/* Run Button */}
                <Button
                    onClick={handleRunCommand}
                    disabled={loading || !workingDir}
                    style={{ background: 'var(--accent-primary)', color: 'white' }}
                >
                    {loading ? 'Running...' : 'Run Command'}
                </Button>

                {/* Output */}
                {result && (
                    <div style={{
                        flex: 1,
                        overflow: 'auto',
                        padding: '1rem',
                        background: result.success ? 'rgba(0, 255, 0, 0.05)' : 'rgba(255, 0, 0, 0.05)',
                        border: `1px solid ${result.success ? 'rgba(0, 255, 0, 0.3)' : 'rgba(255, 0, 0, 0.3)'}`,
                        borderRadius: '4px',
                        fontFamily: 'monospace',
                        fontSize: '0.85rem',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all'
                    }}>
                        <div style={{ marginBottom: '0.5rem', color: result.success ? '#51cf66' : '#ff6b6b', fontWeight: 'bold' }}>
                            $ git {result.command}
                        </div>
                        {result.error ? (
                            <div style={{ color: '#ff6b6b' }}>{result.error}</div>
                        ) : (
                            <div style={{ color: '#e0e0e0' }}>{result.output || '(no output)'}</div>
                        )}
                    </div>
                )}

                {/* Quick Actions */}
                <div style={{ borderTop: '1px solid #333', paddingTop: '0.5rem' }}>
                    <div style={{ fontSize: '0.8rem', color: '#888', marginBottom: '0.5rem' }}>Quick Actions</div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <Button
                            variant="ghost"
                            onClick={() => { setSelectedCommand('status'); setWorkingDir(availableRepos[0] || ''); }}
                            style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                        >
                            Status
                        </Button>
                        <Button
                            variant="ghost"
                            onClick={() => { setSelectedCommand('log --oneline -20'); setWorkingDir(availableRepos[0] || ''); }}
                            style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                        >
                            Recent Commits
                        </Button>
                        <Button
                            variant="ghost"
                            onClick={() => { setSelectedCommand('diff'); setWorkingDir(availableRepos[0] || ''); }}
                            style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                        >
                            Changes
                        </Button>
                    </div>
                </div>
            </GlassPanel>
        </div>
    );
};
