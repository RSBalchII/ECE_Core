import { Application, Request, Response } from 'express';

export function setupGitRoutes(app: Application) {
  // GitHub Repository Ingestion Endpoints (Standard 115)
  // POST /v1/github/repos - Register new repo and trigger initial ingestion
  app.post('/v1/github/repos', async (req: Request, res: Response) => {
    try {
      const body = req.body as any;
      const url = body.url as string;
      const bucket = body.bucket as string;
      const includeHistory = body.include_history === true;

      if (!url || !bucket) {
        res.status(400).json({ error: 'url and bucket are required' });
        return;
      }

      const { GitHubIngestService } = await import('../../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();

      // Register repo
      const repo = await service.registerRepo(url, bucket);

      // Start async ingestion (don't wait for completion)
      (async () => {
        try {
          await service.syncRepo(repo.id);
          if (includeHistory) {
            const token = process.env.GITHUB_TOKEN;
            await service.ingestGitHistory(repo.owner, repo.repo, repo.branch, bucket, token);
            console.log(`[API] Git history ingested for ${repo.owner}/${repo.repo}`);
          }
        } catch (error: any) {
          console.error(`[API] Background sync/history failed for ${repo.id}:`, error);
        }
      })();

      res.status(202).json({
        id: repo.id,
        status: 'ingesting',
        include_history: includeHistory,
        message: `Started ingestion for ${repo.owner}/${repo.repo}${includeHistory ? ' (with full commit history)' : ''}`,
      });
    } catch (error: any) {
      console.error('[API] GitHub repo registration error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/github/repos - List all registered repos
  app.get('/v1/github/repos', async (_req: Request, res: Response) => {
    try {
      const { GitHubIngestService } = await import('../../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();
      const repos = await service.listRepos();
      res.status(200).json(repos);
    } catch (error: any) {
      console.error('[API] GitHub repo list error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // POST /v1/github/repos/:id/sync - Manual sync trigger
  app.post('/v1/github/repos/:id/sync', async (req: Request, res: Response) => {
    try {
      const id = req.params.id as string;

      const { GitHubIngestService } = await import('../../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();

      // Start async sync
      service.syncRepo(id).catch((error: any) => {
        console.error(`[API] Background sync failed for ${id}:`, error);
      });

      res.status(202).json({
        id,
        status: 'syncing',
        message: 'Sync started',
      });
    } catch (error: any) {
      console.error('[API] GitHub sync trigger error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // DELETE /v1/github/repos/:id - Remove repo
  app.delete('/v1/github/repos/:id', async (req: Request, res: Response) => {
    try {
      const id = req.params.id as string;

      const { GitHubIngestService } = await import('../../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();

      const quarantinedCount = await service.removeRepo(id);

      res.status(200).json({
        status: 'removed',
        quarantined_atoms: quarantinedCount,
      });
    } catch (error: any) {
      console.error('[API] GitHub repo removal error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/github/rate-limit - Check GitHub API rate limit status
  app.get('/v1/github/rate-limit', async (_req: Request, res: Response) => {
    try {
      const { GitHubIngestService } = await import('../../services/ingest/github-ingest-service.js');
      const service = new GitHubIngestService();
      const rateLimit = await service.getRateLimitStatus();
      res.status(200).json(rateLimit);
    } catch (error: any) {
      console.error('[API] GitHub rate limit check error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // GET /v1/github/credentials - Check for stored GitHub credentials
  app.get('/v1/github/credentials', async (_req: Request, res: Response) => {
    try {
      const fs = await import('fs');
      const path = await import('path');
      const os = await import('os');

      let token: string | null = null;
      let source: string | null = null;
      let username: string | null = null;

      // 1. Check environment variable
      if (process.env.GITHUB_TOKEN) {
        token = process.env.GITHUB_TOKEN;
        source = 'GITHUB_TOKEN environment variable';
      }

      // 2. Check .netrc file
      if (!token) {
        const netrcPath = path.join(os.homedir(), '.netrc');
        if (fs.existsSync(netrcPath)) {
          const netrcContent = fs.readFileSync(netrcPath, 'utf8');
          const netrcMatch = netrcContent.match(/machine\s+github\.com\s+login\s+(\S+)\s+password\s+(\S+)/);
          if (netrcMatch) {
            username = netrcMatch[1];
            token = netrcMatch[2];
            source = '.netrc file';
          }
        }
      }

      // 3. Check git config for credential helper
      if (!token) {
        // SECURITY FIX #2: Use execFile instead of exec to prevent command injection
        // execFile does not invoke a shell, making it safe from shell injection attacks
        const { execFile } = await import('child_process');
        const util = await import('util');
        const execFilePromise = util.promisify(execFile);

        try {
          // Try to get credential helper status
          const { stdout } = await execFilePromise('git', ['config', '--global', 'credential.helper'], {
            timeout: 5000
          });
          if (stdout.trim()) {
            source = `git credential.helper: ${stdout.trim()}`;
            // Note: We can't directly read credentials from git credential-store
            // without invoking the credential helper, which is complex.
            // We just inform the user that a helper is configured.
          }
        } catch {
          // Git not available or no credential helper
        }
      }

      // If we have a token, validate it and get user info
      let userInfo: { login: string; name?: string } | null = null;
      let tokenValid = false;
      let tokenScopes: string[] = [];

      if (token) {
        try {
          const response = await fetch('https://api.github.com/user', {
            headers: {
              'Authorization': `token ${token}`,
              'Accept': 'application/vnd.github.v3+json',
              'User-Agent': 'anchor-engine-node',
            }
          });

          if (response.ok) {
            const data = await response.json();
            userInfo = { login: data.login, name: data.name };
            tokenValid = true;

            // Get scopes from headers
            const scopesHeader = response.headers.get('x-oauth-scopes');
            if (scopesHeader) {
              tokenScopes = scopesHeader.split(',').map(s => s.trim());
            }
          }
        } catch (error: any) {
          console.error('[API] GitHub token validation error:', error.message);
        }
      }

      const hasCredentials = !!token;
      const canAccessPrivateRepos = tokenValid && (
        tokenScopes.includes('repo') || tokenScopes.includes('public_repo')
      );

      res.status(200).json({
        has_credentials: hasCredentials,
        credential_source: source,
        username: username || userInfo?.login || null,
        user_info: userInfo,
        token_valid: tokenValid,
        scopes: tokenScopes,
        can_access_private_repos: canAccessPrivateRepos,
        message: hasCredentials
          ? (canAccessPrivateRepos
              ? 'GitHub credentials found. You can access both public and private repositories.'
              : 'GitHub credentials found but may be limited to public repositories only.')
          : 'No GitHub credentials found. You can only access public repositories.',
      });
    } catch (error: any) {
      console.error('[API] GitHub credentials check error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // Helper to discover allowed git repositories
  const getDiscoveredRepos = async (): Promise<string[]> => {
    const path = await import('path');
    const fs = await import('fs');
    const { pathManager } = await import('../../utils/path-manager.js');
    const { PROJECT_ROOT } = await import('../../config/paths.js');

    const potentialRepos: string[] = [];
    const basePath = pathManager.getBasePath();
    const checkDirs = [
      basePath,
      path.join(basePath, '..'),
      path.join(basePath, '..', '..'),
      PROJECT_ROOT
    ];

    for (const dir of checkDirs) {
      if (!dir) continue;
      try {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory()) {
            const repoPath = path.join(dir, entry.name);
            const gitPath = path.join(repoPath, '.git');
            // Resolve to absolute path to prevent traversal evasion
            const absoluteRepoPath = path.resolve(repoPath);
            if (fs.existsSync(gitPath) && !potentialRepos.includes(absoluteRepoPath)) {
              potentialRepos.push(absoluteRepoPath);
            }
          }
        }
      } catch {
        // Skip if directory doesn't exist or can't be read
      }
    }
    return potentialRepos;
  };

  // GET /v1/git/repos - List available git repositories
  app.get('/v1/git/repos', async (_req: Request, res: Response) => {
    try {
      const repos = await getDiscoveredRepos();
      res.status(200).json(repos);
    } catch (error: any) {
      console.error('[API] Git repos list error:', error);
      res.status(500).json({ error: error.message });
    }
  });

  // POST /v1/git/run - Execute git command
  app.post('/v1/git/run', async (req: Request, res: Response) => {
    try {
      const { command, working_dir } = req.body;

      if (!command || !working_dir) {
        return res.status(400).json({ error: 'command and working_dir are required' });
      }

      const { execFile } = await import('child_process');
      const util = await import('util');
      const path = await import('path');
      const execFilePromise = util.promisify(execFile);

      // Security: Resolve requested directory to absolute path and verify it's a discovered repository
      const absoluteRequestedDir = path.resolve(working_dir);
      const allowedRepos = await getDiscoveredRepos();

      if (!allowedRepos.includes(absoluteRequestedDir)) {
        console.warn(`[Git] Rejected unauthorized directory access: ${working_dir} (resolved: ${absoluteRequestedDir})`);
        return res.status(403).json({ error: 'Directory not authorized for git commands' });
      }

      // Security: Strict whitelist of allowed git commands and their arguments
      const allowedCommands: Record<string, string[]> = {
        'status': ['status'],
        'log --oneline -20': ['log', '--oneline', '-20'],
        'log --graph --oneline -15': ['log', '--graph', '--oneline', '-15'],
        'diff': ['diff'],
        'diff --cached': ['diff', '--cached'],
        'branch -a': ['branch', '-a'],
        'remote -v': ['remote', '-v']
      };

      if (!(command in allowedCommands)) {
        console.warn(`[Git] Rejected unauthorized command: ${command} in ${absoluteRequestedDir}`);
        return res.status(400).json({ error: 'Command not allowed for security reasons' });
      }

      const args = allowedCommands[command];
      console.log(`[Git] Running: git ${args.join(' ')} in ${absoluteRequestedDir}`);

      try {
        const { stdout, stderr } = await execFilePromise('git', args, {
          cwd: absoluteRequestedDir,
          encoding: 'utf8',
          timeout: 30000 // 30 second timeout
        });

        res.status(200).json({
          command,
          output: stdout || stderr,
          success: true
        });
      } catch (execError: any) {
        // Git command failed - return error output
        res.status(200).json({
          command,
          output: execError.stdout || '',
          error: execError.stderr || execError.message,
          success: false
        });
      }
    } catch (error: any) {
      console.error('[API] Git command execution error:', error);
      res.status(500).json({ error: error.message });
    }
  });
}
