import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { GlassPanel } from '../ui/GlassPanel';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

interface GithubModalProps {
    onClose: () => void;
}

interface GithubCredentials {
    has_credentials: boolean;
    credential_source: string | null;
    username: string | null;
    user_info: { login: string; name?: string } | null;
    token_valid: boolean;
    scopes: string[];
    can_access_private_repos: boolean;
    message: string;
}

export const GithubModal: React.FC<GithubModalProps> = ({ onClose }) => {
    const [repoUrl, setRepoUrl] = useState('');
    const [bucket, setBucket] = useState('');
    const [availableBuckets, setAvailableBuckets] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');

    // Credential status
    const [credentials, setCredentials] = useState<GithubCredentials | null>(null);
    const [checkingCredentials, setCheckingCredentials] = useState(true);

    // New bucket creation state
    const [showNewBucket, setShowNewBucket] = useState(false);
    const [newBucketName, setNewBucketName] = useState('');
    const [newBucketLocation, setNewBucketLocation] = useState<'inbox' | 'external-inbox'>('inbox');
    const [creatingBucket, setCreatingBucket] = useState(false);

    useEffect(() => {
        // Fetch available buckets to populate the dropdown
        api.getBuckets()
            .then(buckets => {
                if (Array.isArray(buckets)) {
                    setAvailableBuckets(buckets);
                    if (buckets.length > 0) {
                        setBucket(buckets[0]);
                    }
                }
            })
            .catch(err => console.error("Failed to load buckets", err));

        // Check GitHub credentials
        api.getGithubCredentials()
            .then(creds => {
                setCredentials(creds);
                setCheckingCredentials(false);
            })
            .catch(err => {
                console.error("Failed to check GitHub credentials", err);
                setCheckingCredentials(false);
            });
    }, []);

    const handleCreateBucket = async () => {
        if (!newBucketName.trim()) {
            setStatusMessage("Error: Bucket name is required.");
            return;
        }

        setCreatingBucket(true);
        setStatusMessage(`Creating bucket "${newBucketName}" in ${newBucketLocation}...`);

        try {
            const result = await api.createBucket(newBucketName.trim(), newBucketLocation);

            if (result.success) {
                setStatusMessage(`Bucket "${result.bucket}" created successfully!`);

                // Refresh bucket list
                const buckets = await api.getBuckets();
                if (Array.isArray(buckets)) {
                    setAvailableBuckets(buckets);
                    setBucket(result.bucket);
                }

                // Reset new bucket form
                setShowNewBucket(false);
                setNewBucketName('');

                setTimeout(() => setStatusMessage(''), 2000);
            } else {
                setStatusMessage(`Error: ${result.error || "Failed to create bucket"}`);
            }
        } catch (e: any) {
            setStatusMessage(`Error: ${e.message}`);
        } finally {
            setCreatingBucket(false);
        }
    };

    const handleIngest = async () => {
        if (!repoUrl.trim()) {
            setStatusMessage("Error: Repository URL is required.");
            return;
        }

        if (!bucket.trim()) {
            setStatusMessage("Error: Target Bucket is required.");
            return;
        }

        setLoading(true);
        setStatusMessage("Initiating ingestion...");

        try {
            const data = await api.ingestGithubRepo(repoUrl, bucket);
            if (data.status === 'ingesting' || data.id) {
                setStatusMessage(`Success! Started ingestion for ${repoUrl}. You can close this window.`);
                setRepoUrl(''); // Clear input on success
            } else {
                setStatusMessage(`Error: ${data.error || "Unknown error occurred"}`);
            }
        } catch (e: any) {
            setStatusMessage(`Error: ${e.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100,
            display: 'flex', justifyContent: 'center', alignItems: 'center'
        }}>
            <GlassPanel className="glass-card" style={{ width: '500px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0 }}>GitHub Repository Ingestion</h3>
                    <Button variant="icon" aria-label="Close modal" onClick={onClose} style={{ fontSize: '1.2rem', color: 'white' }}>✕</Button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label htmlFor="github-url" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Repository URL</label>
                    <Input
                        id="github-url"
                        placeholder="https://github.com/owner/repo"
                        value={repoUrl}
                        onChange={e => setRepoUrl(e.target.value)}
                    />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label htmlFor="target-bucket" style={{ fontSize: '0.9rem', color: '#ccc' }}>Target Bucket</label>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <select
                            id="target-bucket"
                            value={bucket}
                            onChange={e => setBucket(e.target.value)}
                            style={{ flex: 1, padding: '0.5rem', background: '#222', color: 'white', border: '1px solid #444', borderRadius: '4px' }}
                        >
                            <option value="">Select a bucket...</option>
                            {availableBuckets.map(b => (
                                <option key={b} value={b}>{b}</option>
                            ))}
                        </select>
                        <Button
                            variant="ghost"
                            onClick={() => setShowNewBucket(!showNewBucket)}
                            style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem', whiteSpace: 'nowrap' }}
                        >
                            {showNewBucket ? 'Cancel' : '+ New Bucket'}
                        </Button>
                    </div>
                    {availableBuckets.length === 0 && !showNewBucket && (
                        <div style={{ fontSize: '0.8rem', color: '#aaa' }}>Warning: No buckets available. Create one below.</div>
                    )}
                </div>

                {/* New Bucket Creation Form */}
                {showNewBucket && (
                    <div style={{
                        padding: '1rem',
                        background: 'rgba(139, 92, 246, 0.1)',
                        border: '1px solid rgba(139, 92, 246, 0.3)',
                        borderRadius: '4px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.75rem'
                    }}>
                        <div style={{ fontSize: '0.85rem', color: '#aaa', marginBottom: '0.25rem' }}>
                            Create a new bucket for organizing ingested content
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label htmlFor="new-bucket-name" style={{ fontSize: '0.85rem', color: '#ccc' }}>Bucket Name</label>
                            <Input
                                id="new-bucket-name"
                                placeholder="e.g., my-project, research-papers"
                                value={newBucketName}
                                onChange={e => setNewBucketName(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleCreateBucket()}
                                disabled={creatingBucket}
                            />
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label style={{ fontSize: '0.85rem', color: '#ccc' }}>Storage Location</label>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button
                                    onClick={() => setNewBucketLocation('inbox')}
                                    style={{
                                        flex: 1,
                                        padding: '0.5rem',
                                        background: newBucketLocation === 'inbox' ? 'var(--accent-primary)' : '#222',
                                        color: newBucketLocation === 'inbox' ? 'white' : '#ccc',
                                        border: `1px solid ${newBucketLocation === 'inbox' ? 'var(--accent-primary)' : '#444'}`,
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '0.85rem'
                                    }}
                                >
                                    📁 inbox/
                                </button>
                                <button
                                    onClick={() => setNewBucketLocation('external-inbox')}
                                    style={{
                                        flex: 1,
                                        padding: '0.5rem',
                                        background: newBucketLocation === 'external-inbox' ? 'var(--accent-primary)' : '#222',
                                        color: newBucketLocation === 'external-inbox' ? 'white' : '#ccc',
                                        border: `1px solid ${newBucketLocation === 'external-inbox' ? 'var(--accent-primary)' : '#444'}`,
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '0.85rem'
                                    }}
                                >
                                    🌐 external-inbox/
                                </button>
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#888' }}>
                                💡 Tip: Use <strong>inbox/</strong> for internal projects, <strong>external-inbox/</strong> for external data
                            </div>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                            <Button
                                variant="ghost"
                                onClick={() => { setShowNewBucket(false); setNewBucketName(''); }}
                                disabled={creatingBucket}
                                style={{ fontSize: '0.8rem' }}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleCreateBucket}
                                disabled={creatingBucket || !newBucketName.trim()}
                                style={{ fontSize: '0.8rem', background: 'var(--accent-primary)', color: 'white' }}
                            >
                                {creatingBucket ? 'Creating...' : 'Create Bucket'}
                            </Button>
                        </div>
                    </div>
                )}

                {/* GitHub Credential Status */}
                {!checkingCredentials && credentials && (
                    <div style={{
                        padding: '0.75rem',
                        background: credentials.has_credentials
                            ? (credentials.can_access_private_repos
                                ? 'rgba(76, 175, 80, 0.1)'
                                : 'rgba(255, 152, 0, 0.1)')
                            : 'rgba(158, 158, 158, 0.1)',
                        border: `1px solid ${credentials.has_credentials
                            ? (credentials.can_access_private_repos
                                ? 'rgba(76, 175, 80, 0.3)'
                                : 'rgba(255, 152, 0, 0.3)')
                            : 'rgba(158, 158, 158, 0.3)'}`,
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                            <span style={{ fontSize: '1rem' }}>
                                {credentials.has_credentials
                                    ? (credentials.can_access_private_repos ? '✅' : '⚠️')
                                    : 'ℹ️'}
                            </span>
                            <span style={{
                                fontWeight: 600,
                                color: credentials.has_credentials
                                    ? (credentials.can_access_private_repos ? '#4caf50' : '#ff9800')
                                    : '#9e9e9e'
                            }}>
                                {credentials.has_credentials
                                    ? (credentials.can_access_private_repos
                                        ? 'GitHub Authenticated'
                                        : 'Limited Access')
                                    : 'Public Repos Only'}
                            </span>
                        </div>
                        <div style={{ color: '#ccc', marginTop: '0.25rem' }}>
                            {credentials.message}
                        </div>
                        {credentials.username && (
                            <div style={{ color: '#888', marginTop: '0.25rem', fontSize: '0.75rem' }}>
                                User: {credentials.user_info?.name || credentials.username}
                            </div>
                        )}
                        {credentials.has_credentials && !credentials.can_access_private_repos && (
                            <div style={{
                                marginTop: '0.5rem',
                                padding: '0.5rem',
                                background: 'rgba(255, 152, 0, 0.15)',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                color: '#ffb74d'
                            }}>
                                <strong>⚠️ Private repos require full repo scope.</strong>
                                <br />
                                Generate a new PAT at{' '}
                                <a
                                    href="https://github.com/settings/tokens"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ color: '#64b5f6', textDecoration: 'underline' }}
                                >
                                    github.com/settings/tokens
                                </a>{' '}
                                with the <code style={{ background: 'rgba(255,255,255,0.1)', padding: '0.1rem 0.3rem', borderRadius: '2px' }}>repo</code> scope.
                            </div>
                        )}
                        {!credentials.has_credentials && (
                            <div style={{
                                marginTop: '0.5rem',
                                padding: '0.5rem',
                                background: 'rgba(158, 158, 158, 0.15)',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                color: '#bdbdbd'
                            }}>
                                <strong>ℹ️ No credentials stored.</strong>
                                <br />
                                To access private repos, add your PAT to <code style={{ background: 'rgba(255,255,255,0.1)', padding: '0.1rem 0.3rem', borderRadius: '2px' }}>~/.netrc</code> or set the <code style={{ background: 'rgba(255,255,255,0.1)', padding: '0.1rem 0.3rem', borderRadius: '2px' }}>GITHUB_TOKEN</code> env var.
                            </div>
                        )}
                    </div>
                )}

                {checkingCredentials && (
                    <div style={{
                        padding: '0.75rem',
                        background: 'rgba(158, 158, 158, 0.1)',
                        border: '1px solid rgba(158, 158, 158, 0.3)',
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                        color: '#888',
                        textAlign: 'center'
                    }}>
                        Checking GitHub credentials...
                    </div>
                )}

                {statusMessage && (
                    <div style={{
                        marginTop: '0.5rem',
                        padding: '0.5rem',
                        background: statusMessage.startsWith('Error') ? 'rgba(255, 0, 0, 0.1)' : 'rgba(0, 255, 0, 0.1)',
                        border: `1px solid ${statusMessage.startsWith('Error') ? 'rgba(255, 0, 0, 0.3)' : 'rgba(0, 255, 0, 0.3)'}`,
                        borderRadius: '4px',
                        fontSize: '0.85rem',
                        color: statusMessage.startsWith('Error') ? '#ff6b6b' : '#51cf66'
                    }}>
                        {statusMessage}
                    </div>
                )}

                <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                    <Button variant="ghost" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleIngest} disabled={loading || !repoUrl || !bucket}>
                        {loading ? 'Ingesting...' : 'Fetch & Ingest'}
                    </Button>
                </div>
            </GlassPanel>
        </div>
    );
};
