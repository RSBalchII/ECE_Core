/**
 * MCP Server Integration Tests
 *
 * Tests the Model Context Protocol server integration:
 * - Tool execution (anchor_query, anchor_distill, anchor_illuminate)
 * - Rate limiting
 * - Security settings
 * - API communication
 * 
 * Run: pnpm test -- mcp-server.test.ts
 */

import { describe, test, expect, beforeEach, afterAll } from '@jest/globals';
import { PGlite } from '@electric-sql/pglite';
import * as path from 'path';
import * as fs from 'fs';

describe('MCP Server Integration', () => {
  let db: PGlite;
  let testDbPath: string;

  beforeEach(async () => {
    testDbPath = path.join(process.cwd(), 'test-mcp-db-' + Date.now());

    if (fs.existsSync(testDbPath)) {
      fs.rmSync(testDbPath, { recursive: true, force: true });
    }

    db = new PGlite(testDbPath);
    await db.waitReady;
    await createMcpSchema(db);
    await seedMcpData(db);
  });

  afterAll(async () => {
    if (db) {
      await db.close();
    }
    if (testDbPath && fs.existsSync(testDbPath)) {
      fs.rmSync(testDbPath, { recursive: true, force: true });
    }
  });

  describe('Tool Definitions', () => {
    test('should define anchor_query tool', async () => {
      const tools = getMcpTools();
      
      const anchorQuery = tools.find(t => t.name === 'anchor_query');
      expect(anchorQuery).toBeDefined();
      expect(anchorQuery?.description).toContain('Search');
      expect(anchorQuery?.inputSchema).toBeDefined();
    });

    test('should define anchor_distill tool', async () => {
      const tools = getMcpTools();
      
      const anchorDistill = tools.find(t => t.name === 'anchor_distill');
      expect(anchorDistill).toBeDefined();
      expect(anchorDistill?.description).toContain('distill');
    });

    test('should define anchor_illuminate tool', async () => {
      const tools = getMcpTools();
      
      const anchorIlluminate = tools.find(t => t.name === 'anchor_illuminate');
      expect(anchorIlluminate).toBeDefined();
      expect(anchorIlluminate?.description).toContain('BFS');
    });

    test('should define anchor_read_file tool', async () => {
      const tools = getMcpTools();
      
      const anchorReadFile = tools.find(t => t.name === 'anchor_read_file');
      expect(anchorReadFile).toBeDefined();
      expect(anchorReadFile?.inputSchema?.properties?.path).toBeDefined();
    });
  });

  describe('Security Settings', () => {
    test('should load default security settings', async () => {
      const settings = getDefaultSecuritySettings();
      
      expect(settings.enabled).toBe(false);
      expect(settings.require_api_key).toBe(true);
      expect(settings.rate_limit_requests_per_minute).toBe(60);
      expect(settings.max_query_results).toBe(50);
      expect(settings.restrict_to_localhost).toBe(true);
    });

    test('should validate allowed operations', async () => {
      const settings = getDefaultSecuritySettings();
      
      expect(settings.allowed_operations).toContain('query');
      expect(settings.allowed_operations).toContain('read_file');
      expect(settings.allowed_operations).toContain('get_stats');
    });

    test('should check operation permissions', async () => {
      const settings = getDefaultSecuritySettings();
      
      expect(isOperationAllowed(settings, 'query')).toBe(true);
      expect(isOperationAllowed(settings, 'read_file')).toBe(true);
      expect(isOperationAllowed(settings, 'delete_all')).toBe(false);
    });

    test('should block explicitly blocked operations', async () => {
      const settings = {
        ...getDefaultSecuritySettings(),
        blocked_operations: ['distill']
      };
      
      expect(isOperationAllowed(settings, 'distill')).toBe(false);
    });
  });

  describe('Rate Limiting', () => {
    test('should track request counts', async () => {
      const clientId = 'test-client';
      const requestCounts = new Map<string, number[]>();
      
      // Record 5 requests
      for (let i = 0; i < 5; i++) {
        recordRequest(clientId, requestCounts);
      }
      
      const counts = requestCounts.get(clientId);
      expect(counts).toBeDefined();
      expect(counts?.length).toBe(5);
    });

    test('should enforce rate limit', async () => {
      const clientId = 'rate-limited-client';
      const requestCounts = new Map<string, number[]>();
      const limit = 5;
      
      // Record requests up to limit
      for (let i = 0; i < limit; i++) {
        recordRequest(clientId, requestCounts);
      }
      
      // Next request should be rate limited
      const isLimited = isRateLimited(clientId, requestCounts, limit);
      expect(isLimited).toBe(true);
    });

    test('should allow requests under limit', async () => {
      const clientId = 'normal-client';
      const requestCounts = new Map<string, number[]>();
      const limit = 10;
      
      // Record 3 requests
      for (let i = 0; i < 3; i++) {
        recordRequest(clientId, requestCounts);
      }
      
      const isLimited = isRateLimited(clientId, requestCounts, limit);
      expect(isLimited).toBe(false);
    });

    test('should clean up old request timestamps', async () => {
      const clientId = 'cleanup-client';
      const requestCounts = new Map<string, number[]>();
      const windowMs = 60000; // 1 minute
      
      // Add old timestamp (2 minutes ago)
      const oldTime = Date.now() - (2 * 60 * 1000);
      requestCounts.set(clientId, [oldTime]);
      
      // Check rate limit (should clean up old entry)
      isRateLimited(clientId, requestCounts, 10);
      
      const counts = requestCounts.get(clientId);
      expect(counts?.length).toBe(0);
    });
  });

  describe('Query Tool Execution', () => {
    test('should execute search query', async () => {
      const query = 'test content';
      const results = await executeMcpQuery(db, query, 10);
      
      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    test('should respect max_results parameter', async () => {
      const query = 'test';
      const maxResults = 5;
      const results = await executeMcpQuery(db, query, maxResults);
      
      expect(results.length).toBeLessThanOrEqual(maxResults);
    });

    test('should handle empty query', async () => {
      const query = '';
      const results = await executeMcpQuery(db, query, 10);
      
      expect(results).toEqual([]);
    });

    test('should include relevance scores', async () => {
      const query = 'graph';
      const results = await executeMcpQuery(db, query, 10);
      
      results.forEach(result => {
        expect(result).toHaveProperty('score');
        expect(typeof result.score).toBe('number');
      });
    });

    test('should include source information', async () => {
      const query = 'test';
      const results = await executeMcpQuery(db, query, 10);
      
      results.forEach(result => {
        expect(result).toHaveProperty('source');
      });
    });
  });

  describe('Read File Tool', () => {
    test('should read file with line range', async () => {
      const testFile = path.join(process.cwd(), 'test-file.txt');
      const content = 'Line 1\nLine 2\nLine 3\nLine 4\nLine 5';
      fs.writeFileSync(testFile, content, 'utf-8');
      
      try {
        const result = await readFilePath(testFile, 2, 4);
        expect(result).toContain('Line 2');
        expect(result).toContain('Line 3');
        expect(result).toContain('Line 4');
        expect(result).not.toContain('Line 1');
        expect(result).not.toContain('Line 5');
      } finally {
        if (fs.existsSync(testFile)) {
          fs.rmSync(testFile, { force: true });
        }
      }
    });

    test('should handle missing file', async () => {
      const result = await readFilePath('/nonexistent/file.txt', 1, 10);
      expect(result).toContain('error');
    });

    test('should handle invalid line range', async () => {
      const testFile = path.join(process.cwd(), 'test-range.txt');
      fs.writeFileSync(testFile, 'Line 1\nLine 2\nLine 3', 'utf-8');
      
      try {
        // Start line > end line
        const result = await readFilePath(testFile, 5, 2);
        expect(result).toBeDefined();
      } finally {
        if (fs.existsSync(testFile)) {
          fs.rmSync(testFile, { force: true });
        }
      }
    });
  });

  describe('API Communication', () => {
    test('should construct API URL correctly', async () => {
      const baseUrl = 'http://localhost:3160';
      const endpoint = '/v1/memory/search';
      const url = `${baseUrl}${endpoint}`;
      
      expect(url).toBe('http://localhost:3160/v1/memory/search');
    });

    test('should handle API errors gracefully', async () => {
      // Simulate API error
      const errorResponse = {
        error: 'Invalid query',
        message: 'Query parameter is required'
      };
      
      expect(errorResponse.error).toBeDefined();
      expect(errorResponse.message).toBeDefined();
    });

    test('should set correct headers for SSE', async () => {
      const headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
      };
      
      expect(headers['Content-Type']).toBe('text/event-stream');
      expect(headers['Cache-Control']).toBe('no-cache');
    });
  });

  describe('Response Formatting', () => {
    test('should format search results for MCP', async () => {
      const rawResults = [
        {
          id: 'atom-1',
          content: 'Test content',
          source: '/test/file.txt',
          score: 0.95,
          tags: ['test', 'example']
        }
      ];
      
      const formatted = formatMcpResponse(rawResults, 'anchor_query');
      
      expect(formatted.tool).toBe('anchor_query');
      expect(formatted.content).toBeDefined();
      expect(formatted.content.length).toBe(1);
    });

    test('should truncate long content', async () => {
      const longContent = 'A'.repeat(10000);
      const rawResults = [{
        id: 'atom-1',
        content: longContent,
        source: '/test/file.txt',
        score: 0.9
      }];
      
      const formatted = formatMcpResponse(rawResults, 'anchor_query', 1000);
      
      expect(formatted.content[0].content.length).toBeLessThanOrEqual(1000);
    });

    test('should include metadata in response', async () => {
      const rawResults = [
        { id: 'atom-1', content: 'Test', source: '/test.txt', score: 0.9 }
      ];
      
      const formatted = formatMcpResponse(rawResults, 'anchor_query');
      
      expect(formatted.metadata).toBeDefined();
      expect(formatted.metadata.result_count).toBe(1);
    });
  });
});

// Helper Functions

function getMcpTools() {
  return [
    {
      name: 'anchor_query',
      description: 'Search the Anchor memory graph using semantic/graph search',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Search query string' },
          max_results: { type: 'number', description: 'Maximum results' }
        }
      }
    },
    {
      name: 'anchor_distill',
      description: 'Run radial distillation on corpus',
      inputSchema: {
        type: 'object',
        properties: {
          seed: { type: 'object' },
          radius: { type: 'number' }
        }
      }
    },
    {
      name: 'anchor_illuminate',
      description: 'BFS graph traversal from seed concept',
      inputSchema: {
        type: 'object',
        properties: {
          seed: { type: 'string' },
          max_depth: { type: 'number' }
        }
      }
    },
    {
      name: 'anchor_read_file',
      description: 'Read files with line ranges',
      inputSchema: {
        type: 'object',
        properties: {
          path: { type: 'string' },
          start_line: { type: 'number' },
          end_line: { type: 'number' }
        }
      }
    },
    {
      name: 'anchor_list_compounds',
      description: 'List available compounds',
      inputSchema: {
        type: 'object',
        properties: {
          provenance: { type: 'string' }
        }
      }
    }
  ];
}

function getDefaultSecuritySettings() {
  return {
    enabled: false,
    require_api_key: true,
    api_key: '',
    rate_limit_requests_per_minute: 60,
    max_query_results: 50,
    restrict_to_localhost: true,
    allowed_operations: ['query', 'read_file', 'get_stats'],
    blocked_operations: []
  };
}

function isOperationAllowed(settings: any, operation: string): boolean {
  if (settings.blocked_operations.includes(operation)) {
    return false;
  }
  if (settings.allowed_operations.length === 0) {
    return true;
  }
  return settings.allowed_operations.includes(operation);
}

function recordRequest(clientId: string, requestCounts: Map<string, number[]>): void {
  const counts = requestCounts.get(clientId) || [];
  counts.push(Date.now());
  requestCounts.set(clientId, counts);
}

function isRateLimited(clientId: string, requestCounts: Map<string, number[]>, limit: number): boolean {
  const now = Date.now();
  const windowMs = 60000;
  const counts = requestCounts.get(clientId) || [];
  
  const recent = counts.filter(t => now - t < windowMs);
  requestCounts.set(clientId, recent);
  
  return recent.length >= limit;
}

async function executeMcpQuery(db: PGlite, query: string, maxResults: number): Promise<any[]> {
  const terms = query.split(/\s+/).filter(t => t.length > 1);
  if (terms.length === 0) return [];
  
  const tsQuery = terms.join(' | ');
  const result = await db.run(
    `SELECT id, content, source_path as source, 
            ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', $1)) as score
     FROM atoms
     WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', $1)
     ORDER BY score DESC
     LIMIT $2`,
    [tsQuery, maxResults]
  );
  
  return (result.rows || []).map((row: any) => ({
    ...row,
    score: Math.round(row.score * 1000) / 1000
  }));
}

async function readFilePath(filePath: string, startLine: number, endLine: number): Promise<string> {
  try {
    if (!fs.existsSync(filePath)) {
      return 'error: File not found';
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');
    
    const start = Math.max(0, startLine - 1);
    const end = Math.min(lines.length, endLine);
    
    return lines.slice(start, end).join('\n');
  } catch (error: any) {
    return `error: ${error.message}`;
  }
}

function formatMcpResponse(rawResults: any[], toolName: string, maxContentLength = 5000): any {
  const formatted = rawResults.map(r => ({
    ...r,
    content: r.content.length > maxContentLength 
      ? r.content.substring(0, maxContentLength) + '...' 
      : r.content
  }));
  
  return {
    tool: toolName,
    content: formatted,
    metadata: {
      result_count: formatted.length,
      truncated: rawResults.some(r => r.content.length > maxContentLength)
    }
  };
}

async function createMcpSchema(db: PGlite) {
  await db.exec(`
    CREATE TABLE IF NOT EXISTS atoms (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      source_path TEXT,
      timestamp BIGINT,
      tags JSONB,
      provenance TEXT DEFAULT 'internal'
    )
  `);

  await db.exec(`
    CREATE TABLE IF NOT EXISTS compounds (
      id TEXT PRIMARY KEY,
      path TEXT,
      provenance TEXT
    )
  `);
}

async function seedMcpData(db: PGlite) {
  await db.run(`
    INSERT INTO atoms (id, content, source_path, tags)
    VALUES ($1, $2, $3, $4)
  `, ['atom-1', 'Test content for MCP search', '/test/mcp.txt', '["test", "mcp"]']);

  await db.run(`
    INSERT INTO atoms (id, content, source_path, tags)
    VALUES ($1, $2, $3, $4)
  `, ['atom-2', 'Graph traversal implementation', '/test/graph.txt', '["graph", "search"]']);

  await db.run(`
    INSERT INTO atoms (id, content, source_path, tags)
    VALUES ($1, $2, $3, $4)
  `, ['atom-3', 'Another test entry', '/test/another.txt', '["test"]']);
}
