import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { api } from './api';

// Mock data
const mockBuckets = ['inbox', 'code', 'personal', 'dd-data', 'agents', 'news', 'rag'];
const mockTags = ['important', 'work', 'todo', 'archive', 'reference'];
const mockSearchResponse = {
  results: [
    {
      id: 'atom-1',
      content: 'Test search result content',
      source: 'test.md',
      timestamp: Date.now(),
      provenance: 'internal',
      score: 0.95,
      buckets: ['inbox'],
      tags: ['important'],
    },
  ],
  context: 'Test context from backend',
  metadata: {
    atomCount: 1,
    strategy: 'standard',
  },
  split_queries: [],
};

// Setup MSW server
const server = setupServer();

describe('API Service', () => {
  beforeAll(() => {
    server.listen({ onUnhandledRequest: 'error' });
  });

  afterEach(() => {
    server.resetHandlers();
    vi.clearAllMocks();
  });

  afterAll(() => {
    server.close();
  });

  describe('getBuckets', () => {
    it('fetches buckets from API', async () => {
      server.use(
        http.get('/v1/buckets', () => HttpResponse.json(mockBuckets))
      );

      const buckets = await api.getBuckets();

      expect(buckets).toEqual(mockBuckets);
    });

    it('handles API errors', async () => {
      server.use(
        http.get('/v1/buckets', () => HttpResponse.json(
          { error: 'Failed to retrieve buckets' },
          { status: 500 }
        ))
      );

      await expect(api.getBuckets()).resolves.toEqual({ error: 'Failed to retrieve buckets' });
    });
  });

  describe('getTags', () => {
    it('fetches all tags when no buckets specified', async () => {
      server.use(
        http.get('/v1/tags', () => HttpResponse.json(mockTags))
      );

      const tags = await api.getTags();

      expect(tags).toEqual(mockTags);
    });

    it('fetches tags for specific buckets', async () => {
      server.use(
        http.get('/v1/tags', ({ request }) => {
          const url = new URL(request.url);
          const buckets = url.searchParams.get('buckets');
          expect(buckets).toBe('inbox,code');
          return HttpResponse.json(mockTags);
        })
      );

      const tags = await api.getTags(['inbox', 'code']);

      expect(tags).toEqual(mockTags);
    });

    it('handles empty tags array', async () => {
      server.use(
        http.get('/v1/tags', () => HttpResponse.json([]))
      );

      const tags = await api.getTags();

      expect(tags).toEqual([]);
    });
  });

  describe('search', () => {
    it('sends search request with correct parameters', async () => {
      server.use(
        http.post('/v1/memory/search', async ({ request }) => {
          const body = await request.json() as any;

          expect(body).toEqual({
            query: 'test query',
            max_chars: 8192,
            token_budget: 2048,
            provenance: 'internal',
            buckets: ['inbox'],
            tags: ['important'],
            strategy: 'standard',
          });

          return HttpResponse.json(mockSearchResponse);
        })
      );

      const response = await api.search({
        query: 'test query',
        max_chars: 8192,
        token_budget: 2048,
        provenance: 'internal',
        buckets: ['inbox'],
        tags: ['important'],
        strategy: 'standard',
      });

      expect(response.results).toHaveLength(1);
      expect(response.context).toBe('Test context from backend');
    });

    it('uses max-recall strategy when specified', async () => {
      server.use(
        http.post('/v1/memory/search', async ({ request }) => {
          const body = await request.json() as any;
          expect(body.strategy).toBe('max-recall');
          return HttpResponse.json({
            ...mockSearchResponse,
            metadata: { ...mockSearchResponse.metadata, strategy: 'max-recall' },
          });
        })
      );

      const response = await api.search({
        query: 'test query',
        max_chars: 524288,
        token_budget: 131072,
        provenance: 'all',
        strategy: 'max-recall',
      });

      expect(response.metadata.strategy).toBe('max-recall');
    });

    it('parses search results with correct formatting', async () => {
      const formattedResponse = {
        results: [
          {
            id: 'atom-1',
            content: 'Result with special chars: <>&"\'\n\t',
            source: 'inbox/test.md',
            timestamp: Date.now(),
            provenance: 'internal',
            score: 0.95,
            tags: ['test'],
            compound_id: 'mem_1',
            start_byte: 0,
            end_byte: 100,
          },
          {
            id: 'atom-2',
            content: 'Code block:\n```\nconst x = 42;\n```',
            source: 'external-inbox/code.html',
            provenance: 'external',
            score: 0.85,
          },
        ],
        context: 'Formatted context string',
        metadata: {
          atomCount: 2,
          filledPercent: 50,
          budget: 8192,
          tokens_used: 4096,
        },
      };

      server.use(
        http.post('/v1/memory/search', () => HttpResponse.json(formattedResponse))
      );

      const response = await api.search({
        query: 'test',
        max_chars: 8192,
        token_budget: 2048,
        provenance: 'all',
      });

      expect(response.results).toHaveLength(2);
      expect(response.results[0].content).toContain('special chars');
      expect(response.results[1].content).toContain('Code block');
      expect(response.metadata.atomCount).toBe(2);
    });

    it('handles search with empty results', async () => {
      server.use(
        http.post('/v1/memory/search', () => HttpResponse.json({
          results: [],
          context: '',
          metadata: {
            atomCount: 0,
            filledPercent: 0,
            budget: 8192,
            tokens_used: 0,
          },
        }))
      );

      const response = await api.search({
        query: 'nonexistent',
        max_chars: 4096,
        token_budget: 1024,
        provenance: 'internal',
      });

      expect(response.results).toHaveLength(0);
      expect(response.metadata.atomCount).toBe(0);
    });

    it('handles search errors', async () => {
      server.use(
        http.post('/v1/memory/search', () => HttpResponse.json(
          { error: 'Search failed' },
          { status: 500 }
        ))
      );

      await expect(api.search({
        query: 'test',
        max_chars: 4096,
        token_budget: 1024,
        provenance: 'internal',
      })).resolves.toEqual({ error: 'Search failed' });
    });
  });

  describe('quarantineAtom', () => {
    it('quarantines an atom successfully', async () => {
      server.use(
        http.post('/v1/atoms/:atomId/quarantine', ({ params }) => {
          expect(params.atomId).toBe('atom-123');
          return HttpResponse.json({
            status: 'success',
            message: `Atom ${params.atomId} quarantined`,
          });
        })
      );

      const result = await api.quarantineAtom('atom-123');

      expect(result.status).toBe(200);
    });
  });

  describe('backup', () => {
    it('creates backup successfully', async () => {
      server.use(
        http.post('/v1/backup', () => HttpResponse.json({
          status: 'success',
          filename: 'backup-123456.json',
        }))
      );

      const result = await api.backup();

      expect(result.filename).toContain('backup-');
    });
  });

  describe('getQuarantined', () => {
    it('fetches quarantined atoms', async () => {
      server.use(
        http.get('/v1/atoms/quarantined', () => HttpResponse.json([]))
      );

      const result = await api.getQuarantined();

      expect(result).toEqual([]);
    });
  });

  describe('cureAtom', () => {
    it('restores an atom successfully', async () => {
      server.use(
        http.post('/v1/atoms/:atomId/restore', ({ params }) => {
          expect(params.atomId).toBe('atom-123');
          return HttpResponse.json({
            status: 'success',
            message: `Atom ${params.atomId} restored to Graph.`,
          });
        })
      );

      const result = await api.cureAtom('atom-123');

      expect(result.status).toBe('success');
    });
  });

  describe('research', () => {
    it('performs web search', async () => {
      server.use(
        http.get('/v1/research/web-search', () => HttpResponse.json({
          results: [{ title: 'Test Result', url: 'https://example.com' }],
        }))
      );

      const result = await api.research('test query');

      expect(result.results).toHaveLength(1);
    });
  });

  describe('scrape', () => {
    it('scrapes URL with default category', async () => {
      server.use(
        http.post('/v1/research/scrape', async () => HttpResponse.json({
          title: 'Test Article',
          content: 'Scraped content',
        }))
      );

      const result = await api.scrape('https://example.com');

      expect(result.title).toBe('Test Article');
    });

    it('scrapes URL with custom category', async () => {
      server.use(
        http.post('/v1/research/scrape', async ({ request }) => {
          const body = await request.json() as any;
          expect(body.category).toBe('research');
          return HttpResponse.json({
            title: 'Research Paper',
            content: 'Research content',
          });
        })
      );

      const result = await api.scrape('https://example.com', 'research');

      expect(result.title).toBe('Research Paper');
    });
  });

  describe('uploadRaw', () => {
    it('uploads raw content successfully', async () => {
      server.use(
        http.post('/v1/research/upload-raw', async ({ request }) => {
          const body = await request.json() as any;
          expect(body.content).toBe('Test content');
          expect(body.filename).toBe('test.txt');
          return HttpResponse.json({ status: 'success' });
        })
      );

      const result = await api.uploadRaw('Test content', 'test.txt');

      expect(result.status).toBe('success');
    });
  });

  describe('getGraphData', () => {
    it('fetches graph data', async () => {
      server.use(
        http.post('/v1/graph/data', () => HttpResponse.json({
          nodes: [{ id: '1', label: 'Node 1' }],
          links: [],
        }))
      );

      const result = await api.getGraphData('test query', 20);

      expect(result.nodes).toHaveLength(1);
    });
  });

  describe('getPaths', () => {
    it('fetches system paths', async () => {
      server.use(
        http.get('/v1/system/paths', () => HttpResponse.json([
          { path: '/inbox', type: 'watch' },
        ]))
      );

      const result = await api.getPaths();

      expect(result).toHaveLength(1);
    });
  });

  describe('addPath', () => {
    it('adds system path successfully', async () => {
      server.use(
        http.post('/v1/system/paths', () => HttpResponse.json({
          status: 'success',
          message: 'Path added',
        }))
      );

      const result = await api.addPath('/new-path');

      expect(result.status).toBe('success');
    });
  });
});
