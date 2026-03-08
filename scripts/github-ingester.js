#!/usr/bin/env node

/**
 * GitHub Repository Ingester
 * 
 * Fetches a GitHub repository with full metadata and packages it for Anchor Engine ingestion.
 */

import { Octokit } from '@octokit/rest';
import { execSync } from 'child_process';
import { existsSync, mkdirSync, rmSync } from 'fs';
import { join, basename } from 'path';
import { argv } from 'process';
import fs from 'fs/promises';

// Parse command line arguments
function parseArgs() {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--repo' && argv[i + 1]) {
      args.repo = argv[++i];
    } else if (argv[i] === '--branch' && argv[i + 1]) {
      args.branch = argv[++i];
    } else if (argv[i] === '--output' && argv[i + 1]) {
      args.output = argv[++i];
    } else if (argv[i] === '--token' && argv[i + 1]) {
      args.token = argv[++i];
    } else if (argv[i] === '--incremental') {
      args.incremental = true;
    } else if (argv[i] === '--help') {
      console.log(`
GitHub Repository Ingester

Usage:
  node github-ingester.js --repo <owner/repo> [options]

Options:
  --repo       GitHub repository (e.g., RSBalchII/anchor-engine-node) [required]
  --branch     Branch to fetch (default: main)
  --output     Output directory: 'external-inbox' or 'inbox' (default: external-inbox)
  --token      GitHub personal access token (for private repos, higher rate limits)
  --incremental Only fetch new commits since last ingestion
  --help       Show this help message

Examples:
  node github-ingester.js --repo RSBalchII/anchor-engine-node
  node github-ingester.js --repo RSBalchII/anchor-engine-node --branch develop --output inbox
`);
      process.exit(0);
    }
  }
  
  if (!args.repo) {
    console.error('❌ Error: --repo is required');
    console.error('Use --help for usage information');
    process.exit(1);
  }
  
  return {
    repo: args.repo,
    branch: args.branch || 'main',
    output: args.output || 'external-inbox',
    token: args.token || process.env.GITHUB_TOKEN,
    incremental: args.incremental || false
  };
}

// Initialize Octokit
function createOctokit(token) {
  const options = {};
  if (token) {
    options.auth = token;
  }
  return new Octokit(options);
}

// Clone repository
async function cloneRepo(repo, branch, cloneDir) {
  console.log(`📦 Cloning ${repo} (${branch})...`);
  
  if (existsSync(cloneDir)) {
    console.log('🔄 Updating existing clone...');
    execSync(`git pull origin ${branch}`, { cwd: cloneDir, stdio: 'inherit' });
  } else {
    const cloneUrl = `https://github.com/${repo}.git`;
    execSync(`git clone --depth 1 --branch ${branch} ${cloneUrl} ${cloneDir}`, { stdio: 'inherit' });
  }
  
  // Get commit info
  const commitHash = execSync('git rev-parse HEAD', { cwd: cloneDir, encoding: 'utf8' }).trim();
  const commitDate = execSync('git log -1 --format=%ci', { cwd: cloneDir, encoding: 'utf8' }).trim();
  const author = execSync('git log -1 --format=%an', { cwd: cloneDir, encoding: 'utf8' }).trim();
  
  console.log(`✅ Cloned: ${commitHash.substring(0, 8)} by ${author} on ${commitDate}`);
  
  return { commitHash, commitDate, author };
}

// Fetch GitHub metadata
async function fetchMetadata(octokit, owner, repoName, lastIngestionDate = null) {
  console.log('📊 Fetching GitHub metadata...');
  
  const metadata = {
    issues: [],
    pullRequests: [],
    contributors: [],
    releases: [],
    lastFetched: new Date().toISOString()
  };
  
  try {
    // Fetch issues
    console.log('  - Issues...');
    const issues = await octokit.paginate(octokit.rest.issues.listForRepo, {
      owner: owner,
      repo: repoName,
      state: 'all',
      per_page: 100,
      since: lastIngestionDate || undefined
    });
    metadata.issues = issues.map(i => ({
      number: i.number,
      title: i.title,
      body: i.body,
      state: i.state,
      labels: i.labels.map(l => l.name),
      author: i.user?.login,
      createdAt: i.created_at,
      updatedAt: i.updated_at,
      comments: i.comments
    }));
    console.log(`    ✅ ${metadata.issues.length} issues`);
    
    // Fetch pull requests
    console.log('  - Pull Requests...');
    const pulls = await octokit.paginate(octokit.rest.pulls.list, {
      owner: owner,
      repo: repoName,
      state: 'all',
      per_page: 100,
      sort: 'updated',
      direction: 'desc'
    });
    metadata.pullRequests = pulls.map(p => ({
      number: p.number,
      title: p.title,
      body: p.body,
      state: p.state,
      author: p.user?.login,
      createdAt: p.created_at,
      updatedAt: p.updated_at,
      merged: p.merged_at,
      additions: p.additions,
      deletions: p.deletions,
      changedFiles: p.changed_files
    }));
    console.log(`    ✅ ${metadata.pullRequests.length} pull requests`);
    
    // Fetch contributors
    console.log('  - Contributors...');
    const contributors = await octokit.paginate(octokit.rest.repos.listContributors, {
      owner: owner,
      repo: repoName,
      per_page: 100
    });
    metadata.contributors = contributors.map(c => ({
      login: c.login,
      contributions: c.contributions,
      avatar: c.avatar_url
    }));
    console.log(`    ✅ ${metadata.contributors.length} contributors`);
    
    // Fetch releases
    console.log('  - Releases...');
    const releases = await octokit.paginate(octokit.rest.repos.listReleases, {
      owner: owner,
      repo: repoName,
      per_page: 50
    });
    metadata.releases = releases.map(r => ({
      tagName: r.tag_name,
      name: r.name,
      body: r.body,
      author: r.author?.login,
      publishedAt: r.published_at,
      isPrerelease: r.prerelease
    }));
    console.log(`    ✅ ${metadata.releases.length} releases`);
    
  } catch (error) {
    console.warn(`⚠️  Metadata fetch failed: ${error.message}`);
    if (error.status === 401 || error.status === 403) {
      console.warn('   Hint: Use --token for private repos or higher rate limits');
    }
  }
  
  return metadata;
}

// Generate YAML context file
async function generateYaml(repo, branch, commitInfo, metadata, cloneDir) {
  console.log('📝 Generating YAML context...');
  
  const [owner, repoName] = repo.split('/');
  const yamlPath = join(cloneDir, `${repoName}-github.yaml`);
  
  const yamlContent = `# GitHub Repository: ${repo}
# Branch: ${branch}
# Ingested: ${new Date().toISOString()}
# Commit: ${commitInfo.commitHash} by ${commitInfo.author} on ${commitInfo.commitDate}

project: ${repoName}
owner: ${owner}
repository: ${repo}
branch: ${branch}
commit: ${commitInfo.commitHash}
commit_date: ${commitInfo.commitDate}
commit_author: ${commitInfo.author}
ingested_at: ${new Date().toISOString()}

# Contributors (${metadata.contributors.length})
contributors:
${metadata.contributors.slice(0, 20).map(c => `  - ${c.login}: ${c.contributions} contributions`).join('\n')}

# Recent Issues (${metadata.issues.length})
issues:
${metadata.issues.slice(0, 50).map(i => `  - #${i.number}: ${i.title} [${i.state}] by ${i.author}`).join('\n')}

# Recent Pull Requests (${metadata.pullRequests.length})
pull_requests:
${metadata.pullRequests.slice(0, 50).map(p => `  - #${p.number}: ${p.title} [${p.state}]${p.merged ? ' (merged)' : ''} by ${p.author}`).join('\n')}

# Releases (${metadata.releases.length})
releases:
${metadata.releases.slice(0, 20).map(r => `  - ${r.tagName}: ${r.name || 'Untitled'} (${r.publishedAt})`).join('\n')}

# Repository Statistics
stats:
  total_issues: ${metadata.issues.length}
  total_pull_requests: ${metadata.pullRequests.length}
  total_contributors: ${metadata.contributors.length}
  total_releases: ${metadata.releases.length}
  open_issues: ${metadata.issues.filter(i => i.state === 'open').length}
  merged_prs: ${metadata.pullRequests.filter(p => p.merged).length}

# Metadata (full JSON)
metadata_json: |
  ${JSON.stringify(metadata, null, 2).split('\n').map(l => '  ' + l).join('\n')}
`;
  
  // Write YAML file
  await fs.writeFile(yamlPath, yamlContent);
  console.log(`✅ Generated: ${basename(yamlPath)}`);
  
  return yamlPath;
}

// Create tarball using system tar command
async function createTarball(cloneDir, outputPath) {
  console.log('📦 Creating compressed tarball...');
  
  const tarCmd = process.platform === 'win32' 
    ? `tar -czf "${outputPath}" -C "${cloneDir}" .`
    : `tar -czf "${outputPath}" -C "${cloneDir}" .`;
  
  execSync(tarCmd, { stdio: 'pipe' });
  
  // Get file count and size
  const files = await fs.readdir(cloneDir, { recursive: true });
  let fileCount = 0;
  let totalSize = 0;
  
  for (const file of files) {
    const filePath = typeof file === 'string' ? join(cloneDir, file) : file;
    try {
      const stat = await fs.stat(filePath);
      if (stat.isFile() && !file.includes('.git') && !file.includes('node_modules')) {
        fileCount++;
        totalSize += stat.size;
      }
    } catch (e) {
      // File might have been deleted
    }
  }
  
  const sizeMB = (totalSize / 1024 / 1024).toFixed(2);
  console.log(`✅ Created: ${basename(outputPath)} (${fileCount} files, ${sizeMB}MB)`);
  
  return { fileCount, totalSize };
}

// Main function
async function main() {
  const config = parseArgs();
  
  console.log('🚀 GitHub Repository Ingester\n');
  console.log('=' .repeat(60));
  console.log(`Repository: ${config.repo}`);
  console.log(`Branch: ${config.branch}`);
  console.log(`Output: ${config.output}`);
  console.log(`Incremental: ${config.incremental ? 'Yes' : 'No'}`);
  console.log('=' .repeat(60) + '\n');
  
  const [owner, repoName] = config.repo.split('/');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
  const cloneDir = join(process.cwd(), '.github-cache', `${repoName}-${timestamp}`);
  const outputDir = join(process.cwd(), '..', config.output);  // Go up one level to project root
  const tarballPath = join(outputDir, `${repoName}-${config.branch}-${timestamp}.tar.gz`);
  
  try {
    // Ensure output directory exists
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
      console.log(`📁 Created output directory: ${config.output}`);
    }
    
    // Initialize GitHub client
    const octokit = createOctokit(config.token);
    
    // Load last ingestion date for incremental updates
    let lastIngestionDate = null;
    if (config.incremental) {
      const summaryPath = join(outputDir, 'INGEST_SUMMARY.json');
      if (existsSync(summaryPath)) {
        const summary = JSON.parse(await fs.readFile(summaryPath, 'utf8'));
        lastIngestionDate = summary.lastIngestion;
        console.log(`📅 Incremental update since: ${lastIngestionDate}`);
      }
    }
    
    // Clone repository
    await cloneRepo(config.repo, config.branch, cloneDir);
    
    // Fetch metadata
    const metadata = await fetchMetadata(octokit, owner, repoName, lastIngestionDate);
    
    // Get commit info
    const commitHash = execSync('git rev-parse HEAD', { cwd: cloneDir, encoding: 'utf8' }).trim();
    const commitDate = execSync('git log -1 --format=%ci', { cwd: cloneDir, encoding: 'utf8' }).trim();
    const author = execSync('git log -1 --format=%an', { cwd: cloneDir, encoding: 'utf8' }).trim();
    
    // Generate YAML
    await generateYaml(config.repo, config.branch, { commitHash, commitDate, author }, metadata, cloneDir);
    
    // Create tarball
    await createTarball(cloneDir, tarballPath);
    
    // Save ingestion summary
    const summary = {
      repo: config.repo,
      branch: config.branch,
      tarball: basename(tarballPath),
      lastIngestion: new Date().toISOString(),
      commitHash,
      metadata: {
        issues: metadata.issues.length,
        pullRequests: metadata.pullRequests.length,
        contributors: metadata.contributors.length,
        releases: metadata.releases.length
      }
    };
    await fs.writeFile(join(outputDir, 'INGEST_SUMMARY.json'), JSON.stringify(summary, null, 2));
    
    console.log('\n' + '=' .repeat(60));
    console.log('✅ Ingestion complete!');
    console.log('=' .repeat(60));
    console.log(`\n📦 Tarball: ${tarballPath}`);
    console.log(`📄 Summary: ${join(outputDir, 'INGEST_SUMMARY.json')}`);
    console.log('\n💡 Next steps:');
    console.log('   The tarball will be automatically ingested by the Watchdog service.');
    console.log('   Or manually move it to inbox/ for immediate processing.\n');
    
    // Cleanup clone directory
    if (existsSync(cloneDir)) {
      rmSync(cloneDir, { recursive: true, force: true });
      console.log('🧹 Cleaned up temporary files\n');
    }
    
  } catch (error) {
    console.error('\n❌ Ingestion failed:', error.message);
    if (error.response?.status === 404) {
      console.error('   Repository not found or private (use --token)');
    } else if (error.response?.status === 403) {
      console.error('   Rate limit exceeded (use --token for higher limits)');
    }
    process.exit(1);
  }
}

// Run
main().catch(console.error);
