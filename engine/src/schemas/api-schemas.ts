/**
 * Shared Zod Schemas for Anchor Engine API
 *
 * Common schema components used across multiple routes.
 * Import these instead of duplicating validation logic.
 *
 * @see specs/API-ROUTE-MAP.md for route documentation
 */

import { z } from 'zod';

// ============================================
// Base Context Options (Shared across search, explore, distill)
// ============================================

export const contextOptionsSchema = z.object({
  buckets: z.array(z.string()).default([]),
  provenance: z.enum(['internal', 'external', 'all', 'quarantine']).default('all'),
  tags: z.array(z.string()).default([])
});

export type ContextOptions = z.infer<typeof contextOptionsSchema>;

// ============================================
// Search Schemas
// ============================================

export const searchSchema = contextOptionsSchema.extend({
  query: z.string().min(1, "Query cannot be empty"),
  max_chars: z.number().int().positive().max(1000000).default(5000),
  token_budget: z.number().int().positive().max(262144).optional(),
  strategy: z.enum(['standard', 'max-recall']).default('standard'),
  batch_size: z.number().int().positive().max(100).default(20),
  code_weight: z.number().min(0).max(1).optional(),
  user_context: z.any().optional()
});

export type SearchRequest = z.infer<typeof searchSchema>;

export const moleculeSearchSchema = searchSchema.extend({
  deep: z.boolean().default(false)
});

export const maxRecallSearchSchema = searchSchema.extend({
  max_chars: z.number().int().positive().max(1000000).default(16384)
});

// ============================================
// Ingestion Schemas
// ============================================

export const ingestSchema = z.object({
  content: z.string().min(1, "Content cannot be empty").max(10 * 1024 * 1024, "Content too large (max 10MB)"),
  source: z.string().optional(),
  type: z.enum(['text', 'code', 'markdown', 'json', 'html']).optional(),
  bucket: z.string().optional(),
  buckets: z.array(z.string()).default([]),
  tags: z.array(z.string()).max(100, "Too many tags (max 100)").default([])
});

export type IngestRequest = z.infer<typeof ingestSchema>;

// ============================================
// Exploration Schemas
// ============================================

export const exploreSeedSchema = z.object({
  query: z.string().optional(),
  global: z.boolean().optional(),
  atom_ids: z.array(z.string()).optional(),
  compound_ids: z.array(z.string()).optional()
});

export const exploreSchema = contextOptionsSchema.extend({
  seed: exploreSeedSchema.refine(
    (seed) => seed.global || seed.query || seed.atom_ids?.length || seed.compound_ids?.length,
    { message: "Seed must have query, global:true, atom_ids, or compound_ids" }
  ),
  max_depth: z.number().int().positive().max(10).default(3),
  max_nodes: z.number().int().positive().max(1000).default(50),
  format: z.enum(['flat', 'graph']).default('flat')
});

export type ExploreRequest = z.infer<typeof exploreSchema>;

// ============================================
// Distillation Schemas
// ============================================

export const distillSeedSchema = z.object({
  query: z.string().optional(),
  compound_ids: z.array(z.string()).optional(),
  buckets: z.array(z.string()).optional()
});

export const distillSchema = contextOptionsSchema.extend({
  seed: distillSeedSchema.optional(),
  radius: z.number().int().positive().max(10).default(3),
  max_nodes: z.number().int().positive().max(5000).default(500),
  output_format: z.enum(['yaml', 'md']).default('yaml'),
  normalization: z.enum(['strict', 'lenient']).default('strict')
});

export type DistillRequest = z.infer<typeof distillSchema>;

// ============================================
// File Operation Schemas
// ============================================

export const fileReadSchema = z.object({
  path: z.string().min(1, "Path cannot be empty"),
  start_line: z.number().int().nonnegative().optional(),
  end_line: z.number().int().positive().optional()
});

export type FileReadRequest = z.infer<typeof fileReadSchema>;

// ============================================
// System Operation Schemas
// ============================================

export const systemExploreSchema = z.object({
  path: z.string().min(1, "Path cannot be empty")
});

export type SystemExploreRequest = z.infer<typeof systemExploreSchema>;

// ============================================
// Error Response Schema (Standardized)
// ============================================

export const errorResponseSchema = z.object({
  error: z.string(),
  details: z.array(z.object({
    field: z.string(),
    message: z.string()
  })).optional()
});

export type ErrorResponse = z.infer<typeof errorResponseSchema>;
