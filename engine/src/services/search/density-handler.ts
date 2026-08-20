/**
 * Density Handler Module — "The Analyzer"
 * 
 * Handles special query prefixes for density analysis:
 * - "density:" (no term) → full corpus density map (top atoms + tags by frequency)
 * - "density:<term>" → count occurrences of a term, return density tier (light/medium/heavy)
 * - "density:<term1>,<term2>" → multi-term density analysis
 * 
 * Note: "exact:", "fast:", and "deep:" prefixes were removed — regular search
 * handles their purpose. Max-recall is now a context budget toggle on /v1/memory/search,
 * not a separate endpoint or prefix.
 * 
 * Standard 086 Compliant.
 */

import { db } from '../../core/db.js';
import { config } from '../../config/index.js';

export interface DensityTermResult {
  term: string;
  atom_count: number;
  tag_count: number;
  molecule_count: number;
  total_hits: number;
  density_tier: 'light' | 'medium' | 'heavy';
  rag_config: {
    mode: 'fast' | 'balanced' | 'exhaustive';
    doc_limit: number;
    recommendation: string;
  };
}

export interface DensityMapResult {
  atoms: Array<{
    tag: string;
    count: number;
    sources: number;
    density_pct: number;
  }>;
  tags: Array<{
    tag: string;
    bucket: string;
    count: number;
    density_pct: number;
  }>;
  totals: {
    unique_concepts: number;
    unique_tags: number;
    total_occurrences: number;
    tag_occurrences: number;
  };
  rag_thresholds?: typeof config.DENSITY;
}

/** Handle special query prefixes for direct lookups and density analysis. */
export async function handlePrefixQuery(
  query: string,
  buckets: string[] = [],
  maxChars: number = 20000,
  tags: string[] = []
): Promise<any> {
  const prefix = query.trim().toLowerCase();
  
  if (prefix.startsWith('density:')) {
    const searchTerm = prefix.substring(8).trim(); // Remove "density:"
    
    try {
      // Parse multiple comma-separated terms
      const terms = searchTerm ? searchTerm.split(',').map(t => t.trim()).filter(Boolean) : [];
      
      if (terms.length === 0) {
        // "density:" with no term → return full corpus density map
        // Query 1: Top atoms by concept tag frequency (deduplicated by tag)
        // Query 2: Top tags by tag/bucket frequency
        // Execute sequentially — PGlite is single-connection; Promise.all on
        // multiple db.run() calls corrupts connection state (deadlocks subsequent queries).
        const topAtomTags = await db.run(
          `SELECT tag, COUNT(*) as count, COUNT(DISTINCT source_path) as source_count
           FROM atoms, unnest(tags) as tag
           WHERE tags IS NOT NULL AND array_length(tags, 1) > 0
           GROUP BY tag ORDER BY count DESC LIMIT 100`
        );
        const topTags = await db.run(
          'SELECT tag, bucket, COUNT(*) as count FROM tags GROUP BY tag, bucket ORDER BY count DESC LIMIT 50'
        );
        
        const atomTotal = (topAtomTags.rows || []).reduce((sum: number, r: Record<string, unknown>) => sum + parseInt(String(r.count) || '0'), 0);
        const tagTotal = (topTags.rows || []).reduce((sum: number, r: Record<string, unknown>) => sum + parseInt(String(r.count) || '0'), 0);
        
        const densityMap: DensityMapResult = {
          atoms: (topAtomTags.rows || []).map((r: Record<string, unknown>) => ({
            tag: String(r.tag),
            count: parseInt(String(r.count) || '0'),
            sources: parseInt(String(r.source_count) || '0'),
            density_pct: parseFloat((parseInt(String(r.count) || '0') / Math.max(atomTotal, 1) * 100).toFixed(2)),
          })),
          tags: (topTags.rows || []).map((r: Record<string, unknown>) => ({
            tag: String(r.tag),
            bucket: String(r.bucket),
            count: parseInt(String(r.count) || '0'),
            density_pct: parseFloat((parseInt(String(r.count) || '0') / Math.max(tagTotal, 1) * 100).toFixed(2)),
          })),
          totals: { 
            unique_concepts: topAtomTags.rows?.length || 0, 
            unique_tags: topTags.rows?.length || 0, 
            total_occurrences: atomTotal, 
            tag_occurrences: tagTotal 
          },
          rag_thresholds: config.DENSITY,
        };
        
        return {
          context: `Corpus density map — ${densityMap.totals.unique_concepts} unique concepts (${atomTotal} total), ${densityMap.totals.unique_tags} unique tags (${tagTotal} total).`,
          results: (densityMap.atoms || []).map((a) => ({
            id: `density_${a.tag}`,
            content: `${a.tag}: ${a.count} occurrences across ${a.sources} sources`,
            source: a.tag,
            score: a.density_pct / 100,
            tags: [a.tag],
            density: { count: a.count, sources: a.sources, pct: a.density_pct },
          })),
          strategy: 'prefix_density_map',
          metadata: { query_type: 'density_map', ...densityMap.totals, rag_thresholds: densityMap.rag_thresholds },
        };
      }
      
      // "density:<term>" or "density:<term1>,<term2>" → count occurrences per term
      // Counts how many atoms have the term as a tag, how many tags-table rows match,
      // and how many molecules contain atoms with matching tags.
      // Execute sequentially — PGlite is single-connection; Promise.all on multiple
      // db.run() calls causes "cannot drop active portal" errors.
      const densityResults: DensityTermResult[] = [];
      for (const term of terms) {
        // Atoms whose tags array contains a tag matching the search term
        const atomResult = await db.run(
          'SELECT COUNT(*) as count FROM atoms WHERE EXISTS (SELECT 1 FROM unnest(tags) AS t WHERE t ILIKE $1)',
          [`%${term}%`]
        );
        // Tags-table rows where the tag column matches the search term
        const tagResult = await db.run(
          'SELECT COUNT(*) as count FROM tags WHERE tag ILIKE $1',
          [`%${term}%`]
        );
        // Molecules whose joined atoms have a matching tag in their tags array
        const molResult = await db.run(
          `SELECT COUNT(DISTINCT m.id) as count FROM molecules m
           JOIN atoms a ON a.compound_id = m.compound_id
           WHERE EXISTS (SELECT 1 FROM unnest(a.tags) AS t WHERE t ILIKE $1)`,
          [`%${term}%`]
        );
        
        const atomCount = parseInt(atomResult.rows?.[0]?.count || '0', 10);
        const tagCount = parseInt(tagResult.rows?.[0]?.count || '0', 10);
        const molCount = parseInt(molResult.rows?.[0]?.count || '0', 10);
        
        // Use mol_count (actual documents/files) for tier — not noisy atom/tag row counts.
        // This maps directly to how many documents an external RAG pipeline should consider.
        const { LIGHT_DOC_THRESHOLD, MEDIUM_DOC_THRESHOLD, LIGHT_RAG_LIMIT, MEDIUM_RAG_LIMIT, HEAVY_RAG_LIMIT } = config.DENSITY;
        
        let tier: 'light' | 'medium' | 'heavy';
        let rag_limit: number;        // How many docs the external RAG should retrieve
        let rag_mode: string;         // Which mode the external RAG should use
        
        if (molCount >= LIGHT_DOC_THRESHOLD) {
          tier = 'light';
          rag_limit = LIGHT_RAG_LIMIT;
          rag_mode = 'fast';
        } else if (molCount >= MEDIUM_DOC_THRESHOLD) {
          tier = 'medium';
          rag_limit = MEDIUM_RAG_LIMIT;
          rag_mode = 'balanced';
        } else {
          tier = 'heavy';
          rag_limit = HEAVY_RAG_LIMIT;  // 0 = all available
          rag_mode = 'exhaustive';
        }
        
        const result: DensityTermResult = {
          term,
          atom_count: atomCount,
          tag_count: tagCount,
          molecule_count: molCount,
          total_hits: atomCount + tagCount,
          density_tier: tier,
          rag_config: {
            mode: rag_mode as 'fast' | 'balanced' | 'exhaustive',
            doc_limit: rag_limit,
            recommendation: tier === 'light'
              ? `Well-known concept (${molCount} docs). External RAG: retrieve top ${rag_limit} docs in fast mode.`
              : tier === 'medium'
              ? `Moderate concept (${molCount} docs). External RAG: retrieve top ${rag_limit} docs in balanced mode.`
              : `Rare concept (${molCount} docs). External RAG: exhaustive retrieval${rag_limit > 0 ? ` (up to ${rag_limit} docs)` : ' (all available docs)'} + radial distillation.`,
          },
        };
        densityResults.push(result);
      }
      
      const summary = densityResults.map(r => 
        `${r.term}: ${r.molecule_count} docs (${r.density_tier} → ${r.rag_config.mode}, limit ${r.rag_config.doc_limit})`
      ).join(' | ');
      
      return {
        context: `Density analysis: ${summary}`,
        results: densityResults,
        strategy: 'prefix_density_query',
        metadata: {
          query_type: 'density_query',
          terms_analyzed: terms.length,
          tiers: {
            light: densityResults.filter(r => r.density_tier === 'light').length,
            medium: densityResults.filter(r => r.density_tier === 'medium').length,
            heavy: densityResults.filter(r => r.density_tier === 'heavy').length,
          },
        },
      };
    } catch {
      // Density query failed; return safe error response without leaking internals
      return {
        context: `Unable to compute density for "${searchTerm}"`,
        results: [],
        strategy: 'prefix_density_error',
        metadata: {},
      };
    }
  }

  if (prefix.startsWith('distill:')) {
    // Check if it's a list-all-distills query or a specific distill lookup
    const searchTerm = prefix.substring(8).trim();
    
    try {
      if (!searchTerm) {
        // "distill:" with no term → list all distills (Standard 016)
        const result = await db.run('SELECT * FROM distills ORDER BY created_at DESC LIMIT 50');
        const distills = (result.rows || []).map((r: Record<string, unknown>) => ({
          id: String(r.id),
          filename: String(r.filename),
          file_path: String(r.file_path),
          timestamp: String(r.timestamp),
          line_count: parseInt(String(r.line_count) || '0'),
          lines_unique: parseInt(String(r.lines_unique) || '0'),
          compression_ratio: parseFloat(String(r.compression_ratio) || '0'),
        }));
        
        return {
          context: `Found ${distills.length} distillation files (Standard 016)`,
          results: distills,
          strategy: 'prefix_distill_list',
          metadata: { query_type: 'distill_list' },
        };
      } else {
        // "distill:<bucket>" → query specific bucket's distills
        const result = await db.run(
          `SELECT * FROM distills WHERE source_sessions::text ILIKE $1 OR source_files::text ILIKE $1 ORDER BY created_at DESC LIMIT 20`,
          [`%${searchTerm}%`]
        );
        
        return {
          context: `Distill results for "${searchTerm}"`,
          results: (result.rows || []).map((r: Record<string, unknown>) => ({
            id: String(r.id),
            filename: String(r.filename),
            timestamp: String(r.timestamp),
          })),
          strategy: 'prefix_distill_query',
          metadata: { query_type: 'distill_query' },
        };
      }
    } catch {
      return {
        context: `Unable to retrieve distill information for "${searchTerm}"`,
        results: [],
        strategy: 'prefix_distill_error',
        metadata: {},
      };
    }
  }

  // No special prefix matched — return null to let regular search continue
  return null;
}
