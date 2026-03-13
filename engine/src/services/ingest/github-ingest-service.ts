/**
 * GitHub Repository Ingestion Service (Standard 115)
 *
 * Downloads GitHub repository tarballs, extracts source files,
 * and ingests them into the Anchor knowledge graph.
 */

import { gotScraping } from 'got-scraping';
import * as tar from 'tar';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { db } from '../../core/db.js';
import { AtomizerService } from './atomizer-service.js';
import { AtomicIngestService } from './ingest-atomic.js';
import { StructuredLogger } from '../../utils/structured-logger.js';

interface GitHubRepoRecord {
  id: string;
  owner: string;
  repo: string;
  branch: string;
  bucket: string;
  github_url: string;
  last_synced_at?: string;
  last_sync_status?: string;
  last_error?: string;
  total_files: number;
  total_atoms: number;
  total_size_bytes: number;
}

interface SyncResult {
  files_ingested: number;
  atoms_created: number;
  molecules_created: number;
  total_size_bytes: number;
  duration_ms: number;
}

// File exclusion patterns (Standard 115, Section 3.3)
const EXCLUDE_PATTERNS = [
  'node_modules/',
  '.git/',
  'dist/',
  'build/',
  'target/',
  'vendor/',
  '.bin',
  '.exe',
  '.dll',
  '.so',
  '.dylib',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.ico',
  '.pdf',
  '.doc',
  '.docx',
  '.lock', // package-lock.json, Cargo.lock, etc.
];

// Language detection by extension
const LANGUAGE_MAP: Record<string, string> = {
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.js': 'javascript',
  '.jsx': 'javascript',
  '.py': 'python',
  '.rs': 'rust',
  '.go': 'go',
  '.java': 'java',
  '.cpp': 'cpp',
  '.cc': 'cpp',
  '.cxx': 'cpp',
  '.h': 'cpp',
  '.hpp': 'cpp',
  '.c': 'c',
  '.cs': 'csharp',
  '.rb': 'ruby',
  '.php': 'php',
  '.swift': 'swift',
  '.kt': 'kotlin',
  '.scala': 'scala',
  '.ex': 'elixir',
  '.exs': 'elixir',
  '.erl': 'erlang',
  '.hs': 'haskell',
  '.clj': 'clojure',
  '.cljs': 'clojure',
  '.ml': 'ocaml',
  '.fs': 'fsharp',
  '.vue': 'vue',
  '.svelte': 'svelte',
  '.html': 'html',
  '.css': 'css',
  '.scss': 'scss',
  '.sass': 'sass',
  '.less': 'less',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.toml': 'toml',
  '.md': 'markdown',
  '.sql': 'sql',
  '.sh': 'shell',
  '.bash': 'shell',
  '.zsh': 'shell',
  '.ps1': 'powershell',
  '.dockerfile': 'dockerfile',
  '.xml': 'xml',
  '.lua': 'lua',
  '.r': 'r',
  '.R': 'r',
};

export class GitHubIngestService {
  private atomizer: AtomizerService;
  private atomicIngest: AtomicIngestService;

  constructor() {
    this.atomizer = new AtomizerService();
    this.atomicIngest = new AtomicIngestService();
  }

  /**
   * Parse GitHub URL into components
   * Supports:
   * - https://github.com/{owner}/{repo}
   * - https://github.com/{owner}/{repo}/tree/{branch}
   */
  parseGitHubUrl(url: string): { owner: string; repo: string; branch: string } {
    const parsed = new URL(url);
    const parts = parsed.pathname.split('/').filter(Boolean);
    
    if (parts.length < 2) {
      throw new Error(`Invalid GitHub URL: ${url}`);
    }

    const owner = parts[0];
    const repo = parts[1].replace('.git', '');
    
    // Detect branch from /tree/{branch}
    let branch = 'main';
    if (parts[2] === 'tree' && parts[3]) {
      branch = parts[3];
    } else if (parts[2] && !parts[2].includes('.')) {
      // Could be a branch without /tree/
      branch = parts[2];
    }

    return { owner, repo, branch };
  }

  /**
   * Download tarball from GitHub API
   * Returns path to downloaded tarball
   */
  async downloadTarball(
    owner: string,
    repo: string,
    branch: string,
    token?: string
  ): Promise<string> {
    const tarballUrl = `https://api.github.com/repos/${owner}/${repo}/tarball/${branch}`;
    
    const headers: Record<string, string> = {
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'anchor-engine-node',
    };

    if (token) {
      headers['Authorization'] = `token ${token}`;
    }

    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'github-ingest-'));
    const tarballPath = path.join(tempDir, 'repo.tar.gz');

    console.log(`[GitHub] Downloading tarball: ${tarballUrl}`);

    // Retry logic (up to 3 times with exponential backoff)
    let lastError: Error | null = null;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        // Use native fetch for better redirect handling
        const response = await fetch(tarballUrl, {
          headers,
          redirect: 'follow', // Follow redirects automatically
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`GitHub API error: ${response.status} ${response.statusText} - ${errorText}`);
        }

        // Check Content-Type - should be application/octet-stream or application/x-gzip
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          // GitHub returned an error response as JSON instead of tarball
          const errorData = await response.json();
          throw new Error(`GitHub returned JSON instead of tarball: ${JSON.stringify(errorData)}`);
        }

        // Check rate limit headers
        const remaining = response.headers.get('x-ratelimit-remaining');
        const reset = response.headers.get('x-ratelimit-reset');

        if (remaining && parseInt(remaining) < 10) {
          console.warn(`[GitHub] Rate limit warning: ${remaining} requests remaining. Resets at ${reset}`);
        }

        // Get the buffer
        const arrayBuffer = await response.arrayBuffer();
        const buffer = Buffer.from(arrayBuffer);

        // Verify it's a valid tarball (should be > 1KB)
        if (buffer.length < 1024) {
          throw new Error(`Downloaded file too small (${buffer.length} bytes). Likely an API error.`);
        }

        fs.writeFileSync(tarballPath, buffer);
        console.log(`[GitHub] Downloaded ${buffer.length} bytes to ${tarballPath}`);

        return tarballPath;
      } catch (error: any) {
        lastError = error;
        console.warn(`[GitHub] Download attempt ${attempt} failed: ${error.message}`);

        if (attempt < 3) {
          const delay = Math.pow(2, attempt - 1) * 1000; // 1s, 2s, 4s
          console.log(`[GitHub] Retrying in ${delay}ms...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError || new Error('Failed to download tarball after 3 attempts');
  }

  /**
   * Extract tarball to temporary directory
   * Returns path to extracted directory
   */
  async extractTarball(tarballPath: string): Promise<string> {
    const extractDir = path.join(path.dirname(tarballPath), 'extracted');
    fs.mkdirSync(extractDir, { recursive: true });

    console.log(`[GitHub] Extracting tarball to ${extractDir}`);

    await tar.x({
      file: tarballPath,
      cwd: extractDir,
      strip: 1, // Remove top-level directory (owner-repo-hash)
    });

    return extractDir;
  }

  /**
   * Check if file is binary by checking for null bytes
   */
  async isBinaryFile(filePath: string): Promise<boolean> {
    try {
      const fd = await fs.promises.open(filePath, 'r');
      const buffer = Buffer.alloc(8192); // Check first 8KB
      await fd.read(buffer, 0, 8192, 0);
      await fd.close();

      // Check for null bytes (common in binary files)
      for (let i = 0; i < buffer.length; i++) {
        if (buffer[i] === 0) {
          return true;
        }
      }

      return false;
    } catch {
      return true; // Assume binary if we can't read it
    }
  }

  /**
   * Detect programming language from file extension
   */
  detectLanguage(filePath: string): string {
    const ext = path.extname(filePath).toLowerCase();
    const basename = path.basename(filePath).toLowerCase();
    
    // Check for special filenames first
    if (basename === 'dockerfile') return 'dockerfile';
    if (basename === 'makefile') return 'makefile';
    
    return LANGUAGE_MAP[ext] || 'unknown';
  }

  /**
   * Check if file should be excluded
   */
  shouldExclude(filePath: string): boolean {
    const relativePath = filePath.toLowerCase();
    
    return EXCLUDE_PATTERNS.some(pattern => {
      if (pattern.startsWith('.')) {
        // Extension check
        return relativePath.endsWith(pattern);
      } else {
        // Directory/path check
        return relativePath.includes(pattern);
      }
    });
  }

  /**
   * Walk directory and return list of source files
   */
  async walkDirectory(dir: string, baseDir: string = dir): Promise<string[]> {
    const files: string[] = [];
    
    try {
      const entries = await fs.promises.readdir(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        // Skip excluded paths
        if (this.shouldExclude(fullPath)) {
          continue;
        }

        if (entry.isDirectory()) {
          const subFiles = await this.walkDirectory(fullPath, baseDir);
          files.push(...subFiles);
        } else if (entry.isFile()) {
          // Skip binary files
          const isBinary = await this.isBinaryFile(fullPath);
          if (!isBinary) {
            files.push(fullPath);
          }
        }
      }
    } catch (error: any) {
      console.warn(`[GitHub] Error walking directory ${dir}: ${error.message}`);
    }

    return files;
  }

  /**
   * Register a new GitHub repository in the database
   */
  async registerRepo(url: string, bucket: string): Promise<GitHubRepoRecord> {
    const { owner, repo, branch } = this.parseGitHubUrl(url);
    
    // Generate unique ID
    const id = `github_${owner}_${repo}_${branch}`;
    
    console.log(`[GitHub] Registering repo: ${owner}/${repo} (branch: ${branch})`);

    // Insert or update record
    await db.run(
      `INSERT INTO github_repos (id, owner, repo, branch, bucket, github_url, last_sync_status)
       VALUES ($1, $2, $3, $4, $5, $6, 'pending')
       ON CONFLICT (id) DO UPDATE SET
         bucket = $5,
         github_url = $6,
         updated_at = CURRENT_TIMESTAMP`,
      [id, owner, repo, branch, bucket, url]
    );

    return {
      id,
      owner,
      repo,
      branch,
      bucket,
      github_url: url,
      total_files: 0,
      total_atoms: 0,
      total_size_bytes: 0,
    };
  }

  /**
   * Sync a repository (download, extract, ingest)
   */
  async syncRepo(repoIdOrRecord: string | GitHubRepoRecord): Promise<SyncResult> {
    const startTime = Date.now();

    let repo: GitHubRepoRecord;

    // Accept either repo ID (lookup required) or repo object directly
    if (typeof repoIdOrRecord === 'string') {
      // Get repo record by ID
      const result = await db.run(
        `SELECT * FROM github_repos WHERE id = $1`,
        [repoIdOrRecord]
      );

      if (!result.rows || result.rows.length === 0) {
        throw new Error(`Repository not found: ${repoIdOrRecord}`);
      }

      repo = result.rows[0] as GitHubRepoRecord;
    } else {
      // Repo object passed directly (avoids race condition)
      repo = repoIdOrRecord;
    }

    console.log(`[GitHub] Syncing ${repo.owner}/${repo.repo} (bucket: ${repo.bucket})`);

    // Update status to in_progress
    await db.run(
      `UPDATE github_repos SET last_sync_status = 'in_progress', last_error = NULL WHERE id = $1`,
      [repo.id]
    );

    try {
      // Get GitHub token from env (optional)
      const token = process.env.GITHUB_TOKEN;

      // Download tarball
      const tarballPath = await this.downloadTarball(repo.owner, repo.repo, repo.branch, token);

      // Extract tarball
      const extractDir = await this.extractTarball(tarballPath);

      // Walk directory and get files
      const files = await this.walkDirectory(extractDir);
      console.log(`[GitHub] Found ${files.length} source files`);

      // Quarantine old atoms from this repo (Standard 115, Section 4.5)
      await this.quarantineOldAtoms(repo.id);

      // Ingest each file
      let filesIngested = 0;
      let totalAtoms = 0;
      let totalMolecules = 0;
      let totalSize = 0;

      for (const file of files) {
        try {
          const content = await fs.promises.readFile(file, 'utf8');
          const relativePath = path.relative(extractDir, file);
          
          // Construct source path: github:{owner}/{repo}/{filepath}
          const sourcePath = `github:${repo.owner}/${repo.repo}/${relativePath}`;
          
          console.log(`[GitHub] Ingesting: ${relativePath}`);

          // Atomize
          const atomizeResult = await this.atomizer.atomize(
            content,
            sourcePath,
            'external'
          );

          // Skip if transient data detected
          if (!atomizeResult) {
            console.log(`[GitHub] ⚠️ SKIP: ${relativePath} - Transient data`);
            continue;
          }

          const { compound, molecules, atoms } = atomizeResult;

          // Ingest
          await this.atomicIngest.ingestResult(compound, molecules, atoms, [repo.bucket]);

          filesIngested++;
          totalAtoms += atoms.length;
          totalMolecules += molecules.length;
          totalSize += Buffer.byteLength(content, 'utf8');

          // Yield to event loop periodically
          if (filesIngested % 10 === 0) {
            await new Promise(resolve => setImmediate(resolve));
          }
        } catch (error: any) {
          console.warn(`[GitHub] Failed to ingest ${file}: ${error.message}`);
        }
      }

      // Cleanup temp directory
      await fs.promises.rm(path.dirname(tarballPath), { recursive: true, force: true });

      // Update repo record
      await db.run(
        `UPDATE github_repos SET
          last_synced_at = CURRENT_TIMESTAMP,
          last_sync_status = 'success',
          total_files = $1,
          total_atoms = $2,
          total_size_bytes = $3,
          updated_at = CURRENT_TIMESTAMP
         WHERE id = $4`,
        [filesIngested, totalAtoms, totalSize, repo.id]
      );

      const duration = Date.now() - startTime;
      console.log(`[GitHub] Sync complete: ${filesIngested} files, ${totalAtoms} atoms in ${(duration / 1000).toFixed(1)}s`);

      return {
        files_ingested: filesIngested,
        atoms_created: totalAtoms,
        molecules_created: totalMolecules,
        total_size_bytes: totalSize,
        duration_ms: duration,
      };
    } catch (error: any) {
      // Update status to failed
      await db.run(
        `UPDATE github_repos SET last_sync_status = 'failed', last_error = $1 WHERE id = $2`,
        [error.message, repo.id]
      );

      throw error;
    }
  }

  /**
   * Quarantine old atoms from a repository
   */
  private async quarantineOldAtoms(repoIdOrRecord: string | GitHubRepoRecord): Promise<void> {
    let owner: string, repo: string;

    if (typeof repoIdOrRecord === 'string') {
      const result = await db.run(
        `SELECT owner, repo FROM github_repos WHERE id = $1`,
        [repoIdOrRecord]
      );

      if (!result.rows || result.rows.length === 0) return;

      owner = result.rows[0].owner;
      repo = result.rows[0].repo;
    } else {
      owner = repoIdOrRecord.owner;
      repo = repoIdOrRecord.repo;
    }

    const sourcePrefix = `github:${owner}/${repo}/`;

    console.log(`[GitHub] Quarantining old atoms with source_path LIKE '${sourcePrefix}%'`);

    // Add #quarantined tag to old atoms
    await db.run(
      `UPDATE atoms SET
        tags = array_cat(COALESCE(tags, '{}'), ARRAY['#quarantined']),
        provenance = 'quarantine'
       WHERE source_path LIKE $1`,
      [`${sourcePrefix}%`]
    );
  }

  /**
   * List all registered GitHub repositories
   */
  async listRepos(): Promise<GitHubRepoRecord[]> {
    const result = await db.run(
      `SELECT * FROM github_repos ORDER BY created_at DESC`
    );

    return result.rows || [];
  }

  /**
   * Remove a repository from the registry
   */
  async removeRepo(repoId: string): Promise<number> {
    // First, quarantine all atoms from this repo
    const result = await db.run(
      `SELECT owner, repo FROM github_repos WHERE id = $1`,
      [repoId]
    );

    let quarantinedCount = 0;
    if (result.rows && result.rows.length > 0) {
      const { owner, repo } = result.rows[0];
      const sourcePrefix = `github:${owner}/${repo}/`;

      const updateResult = await db.run(
        `UPDATE atoms SET
          tags = array_cat(COALESCE(tags, '{}'), ARRAY['#quarantined']),
          provenance = 'quarantine'
         WHERE source_path LIKE $1`,
        [`${sourcePrefix}%`]
      );

      quarantinedCount = updateResult.rowCount || 0;
    }

    // Delete repo record
    await db.run(
      `DELETE FROM github_repos WHERE id = $1`,
      [repoId]
    );

    return quarantinedCount;
  }

  /**
   * Fetch full commit history from GitHub API and ingest as searchable molecules.
   * Each commit becomes its own paragraph: sha, author, date, message, files changed.
   * The entire history is ingested as one compound: github:{owner}/{repo}/commit-history.md
   */
  async ingestGitHistory(
    owner: string,
    repo: string,
    branch: string,
    bucket: string,
    token?: string
  ): Promise<number> {
    const headers: Record<string, string> = {
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'anchor-engine-node',
    };
    if (token) headers['Authorization'] = `token ${token}`;

    const commits: string[] = [];
    let page = 1;
    const PER_PAGE = 100;

    console.log(`[GitHub] Fetching commit history for ${owner}/${repo} (branch: ${branch})`);

    while (true) {
      const url = `https://api.github.com/repos/${owner}/${repo}/commits?sha=${branch}&per_page=${PER_PAGE}&page=${page}`;
      const res = await fetch(url, { headers });

      if (!res.ok) {
        console.warn(`[GitHub] Commits API error ${res.status} on page ${page} — stopping`);
        break;
      }

      const data = await res.json() as any[];
      if (!Array.isArray(data) || data.length === 0) break;

      for (const c of data) {
        const sha = (c.sha || '').slice(0, 12);
        const author = c.commit?.author?.name || c.author?.login || 'unknown';
        const date = c.commit?.author?.date || '';
        const message = (c.commit?.message || '').trim();
        const filesLine = Array.isArray(c.files)
          ? c.files.map((f: any) => `  ${f.status[0].toUpperCase()} ${f.filename} (+${f.additions} -${f.deletions})`).join('\n')
          : '';

        commits.push(
          `## ${sha} — ${date}\nAuthor: ${author}\n\n${message}${filesLine ? '\n\nFiles:\n' + filesLine : ''}`
        );
      }

      console.log(`[GitHub] Fetched page ${page} (${data.length} commits, total so far: ${commits.length})`);

      // Check Link header for next page
      const linkHeader = res.headers.get('link') || '';
      if (!linkHeader.includes('rel="next"')) break;
      page++;

      // Yield to event loop between pages
      await new Promise(resolve => setImmediate(resolve));
    }

    if (commits.length === 0) {
      console.log(`[GitHub] No commits found for ${owner}/${repo}`);
      return 0;
    }

    const historyContent = `# Git History: ${owner}/${repo} (${branch})\n\nTotal commits: ${commits.length}\n\n---\n\n${commits.join('\n\n---\n\n')}`;
    const sourcePath = `github:${owner}/${repo}/commit-history.md`;

    console.log(`[GitHub] Ingesting ${commits.length} commits as ${sourcePath}`);

    const atomizeResult = await this.atomizer.atomize(historyContent, sourcePath, 'external');
    if (atomizeResult) {
      const { compound, molecules, atoms } = atomizeResult;
      await this.atomicIngest.ingestResult(compound, molecules, atoms, [bucket, 'git-history']);
    }

    return commits.length;
  }


  async getRateLimitStatus(): Promise<{
    limit: number;
    remaining: number;
    reset_at: string;
    authenticated: boolean;
  }> {
    const token = process.env.GITHUB_TOKEN;
    const url = token
      ? 'https://api.github.com/rate_limit'
      : 'https://api.github.com/rate_limit';

    try {
      const headers: Record<string, string> = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'anchor-engine-node',
      };

      if (token) {
        headers['Authorization'] = `token ${token}`;
      }

      const response = await gotScraping(url, { headers });
      const data = JSON.parse(response.body);

      const core = data.resources.core;

      return {
        limit: core.limit,
        remaining: core.remaining,
        reset_at: new Date(core.reset * 1000).toISOString(),
        authenticated: !!token,
      };
    } catch (error: any) {
      console.error(`[GitHub] Failed to get rate limit: ${error.message}`);
      
      // Return conservative defaults
      return {
        limit: 60,
        remaining: 0,
        reset_at: new Date(Date.now() + 3600000).toISOString(),
        authenticated: false,
      };
    }
  }
}
