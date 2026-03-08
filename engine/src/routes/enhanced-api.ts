/**
 * Enhanced API Routes for ECE
 *
 * Implements additional endpoints for the enhanced functionality
 * following Standard 058: UniversalRAG API
 */

import { Application, Request, Response } from 'express';
import { executeSearch, getGlobalTags } from '../services/search/search.js';
import { db } from '../core/db.js';

// Placeholder functions for bright nodes functionality
const getBrightNodes = async (query: string, buckets: string[], maxNodes: number) => {
  console.warn('Bright nodes functionality not implemented yet');
  return [];
};

const getStructuredGraph = async (query: string, buckets: string[]) => {
  console.warn('Structured graph functionality not implemented yet');
  return {};
};

export function setupEnhancedRoutes(app: Application) {
  // Enhanced search endpoint with Bright Node support
  app.post('/v1/memory/search-enhanced', async (req: Request, res: Response) => {
    try {
      const { query, buckets, maxChars, provenance, includeGraph, user_context } = req.body;

      // Default values
      const searchQuery = query || '';
      const searchBuckets = buckets || [];
      const maxCharacters = maxChars || 524288;
      const searchProvenance = provenance || 'all';
      const includeGraphData = includeGraph || false;

      // Perform standard search
      const searchResults = await executeSearch(
        searchQuery,
        undefined,
        searchBuckets,
        maxCharacters,
        false,
        searchProvenance,
        [], // explicitTags
        undefined, // filters
        false, // useMaxRecall
        user_context
      );

      // Optionally include Bright Node graph data
      let graphData = null;
      if (includeGraphData) {
        graphData = await getStructuredGraph(searchQuery, searchBuckets);
      }

      res.status(200).json({
        query: searchQuery,
        results: searchResults.results,
        context: searchResults.context,
        graph: graphData,
        metadata: searchResults.metadata
      });
    } catch (error: any) {
      console.error('Enhanced search failed:', error);
      res.status(500).json({
        error: error.message,
        query: req.body?.query || ''
      });
    }
  });

  // Bright Node Protocol endpoint
  app.post('/v1/memory/bright-nodes', async (req: Request, res: Response) => {
    try {
      const { query, buckets, maxNodes } = req.body;

      const searchQuery = query || '';
      const searchBuckets = buckets || [];
      const maxNodeCount = maxNodes || 50;

      const brightNodes = await getBrightNodes(searchQuery, searchBuckets, maxNodeCount);

      res.status(200).json({
        query: searchQuery,
        nodes: brightNodes,
        count: brightNodes.length,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      console.error('Bright Nodes request failed:', error);
      res.status(500).json({
        error: error.message,
        query: req.body?.query || ''
      });
    }
  });

  // Structured Graph endpoint for reasoning models
  app.post('/v1/memory/graph-structure', async (req: Request, res: Response) => {
    try {
      const { query, buckets } = req.body;

      const searchQuery = query || '';
      const searchBuckets = buckets || [];

      const graphStructure = await getStructuredGraph(searchQuery, searchBuckets);

      res.status(200).json(graphStructure);
    } catch (error: any) {
      console.error('Graph structure request failed:', error);
      res.status(500).json({
        error: error.message,
        query: req.body?.query || ''
      });
    }
  });

  // Global tags endpoint
  app.get('/v1/memory/tags/global', async (_req: Request, res: Response) => {
    try {
      const tags = await getGlobalTags();

      res.status(200).json({
        tags,
        count: tags.length,
        timestamp: new Date().toISOString()
      });
    } catch (error: any) {
      console.error('Global tags request failed:', error);
      res.status(500).json({
        error: error.message
      });
    }
  });

  // System information endpoint
  app.get('/v1/system/info', async (_req: Request, res: Response) => {
    try {
      // Get basic system information
      const systemInfo = {
        version: '3.0.0',
        uptime: process.uptime(),
        timestamp: new Date().toISOString(),
        nodeVersion: process.version,
        platform: process.platform,
        arch: process.arch,
        pid: process.pid,
        memoryUsage: process.memoryUsage(),
        env: {
          NODE_ENV: process.env.NODE_ENV,
          ECE_ENV: process.env.ECE_ENV
        }
      };

      res.status(200).json(systemInfo);
    } catch (error: any) {
      console.error('System info request failed:', error);
      res.status(500).json({
        error: error.message
      });
    }
  });
}