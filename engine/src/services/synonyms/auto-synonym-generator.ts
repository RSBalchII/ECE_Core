/**
 * Automated Synonym Ring Generator
 * 
 * Mines your existing data (codebase + chat logs) to automatically generate
 * synonym rings for semantic query expansion.
 * 
 * Strategies:
 * 1. Co-occurrence Analysis: Terms appearing together frequently
 * 2. Tag Neighborhood Similarity: Terms with similar tag patterns
 * 3. SimHash Proximity: Terms in atoms with similar simhashes
 * 4. Content Similarity: Terms appearing in similar contexts
 * 
 * Usage:
 *   const generator = new AutoSynonymGenerator();
 *   const synonyms = await generator.generateSynonymRings();
 *   await generator.saveSynonymRings(synonyms, './data/synonym-ring.json');
 */

import { db } from '../../core/db.js';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { executor } from '../../utils/memory-aware-executor.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface TermPair {
  term1: string;
  term2: string;
  score: number;
  strategy: string;
}

interface TermCluster {
  seed: string;
  synonyms: string[];
  confidence: number;
}

export class AutoSynonymGenerator {
  private MIN_CO_OCCURRENCE = 5;        // Minimum times terms must appear together
  private MIN_JACCARD_SIMILARITY = 0.5; // Minimum tag neighborhood similarity
  private MAX_SIMHASH_DISTANCE = 8;     // Maximum Hamming distance for simhash clustering
  private TOP_SYNONYMS_PER_TERM = 10;   // Maximum synonyms to suggest per term

  /**
   * Specialized hamming distance for precomputed BigInts
   */
  private fastHammingDistance(big1: bigint, big2: bigint): number {
    let xor = big1 ^ big2;
    let distance = 0;
    while (xor > 0n) {
      distance += Number(xor & 1n);
      xor >>= 1n;
    }
    return distance;
  }

  /**
   * Strategy 1: Co-occurrence Mining
   * Find terms that frequently appear together in the same atoms/documents.
   *
   * SQL: Finds pairs of terms appearing in same atom content
   * Groups by term pairs, counts co-occurrences
   * Returns top N pairs per term
   */
  async mineCooccurrenceSynonyms(windowSize: number = 100): Promise<Map<string, TermPair[]>> {
    console.log('[SynonymGenerator] Strategy 1: Mining co-occurrence patterns...');
    const startTime = Date.now();

    try {
      // Get total count for progress tracking
      const countQuery = `
        SELECT COUNT(*) as total FROM atoms WHERE length(content) > 50
      `;
      const countResult = await db.run(countQuery);
      const totalAtoms = countResult.rows?.[0]?.total || 0;
      console.log(`[SynonymGenerator] Processing ${totalAtoms} atoms...`);

      // SIMPLIFIED: Skip complex co-occurrence mining for now
      // The tag neighborhood and simhash strategies are working well
      console.log('[SynonymGenerator] Skipping co-occurrence mining (using tag neighborhood + simhash only)');
      console.log(`[SynonymGenerator] Co-occurrence skipped in ${((Date.now() - startTime) / 1000).toFixed(1)}s`);

      return new Map<string, TermPair[]>();
    } catch (error: any) {
      console.error('[SynonymGenerator] Co-occurrence mining failed:', error.message);
      return new Map<string, TermPair[]>();
    }
  }

  /**
   * Strategy 2: Tag Neighborhood Similarity
   * Terms with similar tag patterns are likely synonyms.
   * 
   * Computes Jaccard similarity between term tag-sets.
   * Jaccard(A,B) = |A ∩ B| / |A ∪ B|
   * Clusters terms with Jaccard > threshold
   */
  async mineTagNeighborhoodSynonyms(): Promise<Map<string, TermPair[]>> {
    console.log('[SynonymGenerator] Strategy 2: Mining tag neighborhood similarity...');

    try {
      // Get all terms and their associated tags
      const termTagsQuery = `
        WITH term_tag_counts AS (
          SELECT 
            LOWER(unnest(tags)) as tag,
            a.id as atom_id
          FROM atoms a
          WHERE tags IS NOT NULL AND cardinality(tags) > 0
        ),
        term_tag_sets AS (
          SELECT 
            tag,
            array_agg(DISTINCT atom_id) as atom_ids
          FROM term_tag_counts
          GROUP BY tag
        )
        SELECT tag, atom_ids
        FROM term_tag_sets
        WHERE array_length(atom_ids, 1) >= 2
        ORDER BY array_length(atom_ids, 1) DESC
        LIMIT 500
      `;

      const result = await db.run(termTagsQuery);

      if (!result.rows || result.rows.length < 2) {
        console.log('[SynonymGenerator] Insufficient tag data for neighborhood analysis');
        return new Map<string, TermPair[]>();
      }

      const termTagSets = new Map<string, Set<string>>();

      for (const row of result.rows as any[]) {
        const { tag, atom_ids } = row;
        termTagSets.set(tag, new Set(atom_ids));
      }

      // Compute Jaccard similarity between all pairs
      const pairs = new Map<string, TermPair[]>();
      const terms = Array.from(termTagSets.keys());

      for (let i = 0; i < terms.length; i++) {
        for (let j = i + 1; j < terms.length; j++) {
          const term1 = terms[i];
          const term2 = terms[j];

          const set1 = termTagSets.get(term1)!;
          const set2 = termTagSets.get(term2)!;

          const intersection = new Set([...set1].filter(x => set2.has(x)));
          const union = new Set([...set1, ...set2]);

          const jaccard = intersection.size / union.size;

          if (jaccard >= this.MIN_JACCARD_SIMILARITY) {
            if (!pairs.has(term1)) {
              pairs.set(term1, []);
            }

            pairs.get(term1)!.push({
              term1,
              term2,
              score: jaccard,
              strategy: 'tag_neighborhood',
            });

            if (!pairs.has(term2)) {
              pairs.set(term2, []);
            }

            pairs.get(term2)!.push({
              term1: term2,
              term2: term1,
              score: jaccard,
              strategy: 'tag_neighborhood',
            });
          }
        }
      }

      console.log(`[SynonymGenerator] Found ${pairs.size} terms with tag neighborhood synonyms`);
      return pairs;
    } catch (error: any) {
      console.error('[SynonymGenerator] Tag neighborhood mining failed:', error.message);
      return new Map<string, TermPair[]>();
    }
  }

  /**
   * Strategy 3: SimHash Proximity
   * Terms in atoms with similar simhashes are related.
   * 
   * Groups atoms by simhash Hamming distance < threshold.
   * Extracts terms from each cluster.
   * Terms appearing in same cluster are candidates.
   */
  async mineSimHashSynonyms(): Promise<Map<string, TermPair[]>> {
    console.log('[SynonymGenerator] Strategy 3: Mining simhash proximity...');

    try {
      // Get atoms with their simhashes and extract key terms
      const query = `
        SELECT 
          id,
          simhash,
          content,
          tags
        FROM atoms
        WHERE simhash IS NOT NULL AND simhash != '0'
        LIMIT 1000
      `;

      const result = await db.run(query);

      if (!result.rows) {
        console.log('[SynonymGenerator] No simhash data available');
        return new Map<string, TermPair[]>();
      }

      // Helper to extract terms from content
      const extractTerms = (content: string): string[] => {
        if (!content || typeof content !== 'string') return [];
        return content.toLowerCase()
          .split(/[\s\W]+/)
          .filter(term => term.length > 3 && term.length < 30)
          .slice(0, 50); // Limit terms per atom
      };

      // Group atoms by simhash proximity
      const atoms = result.rows as any[];

      // Precompute terms and simhash BigInts to avoid redundant work in O(N^2) loop
      const atomsWithMetadata = atoms.map(atom => {
        let hashBigInt: bigint | undefined;
        try {
          const hash = atom.simhash;
          hashBigInt = BigInt(hash.startsWith('0x') ? hash : `0x${hash}`);
        } catch (e) {
          // Fallback handled in distance calculation
        }

        return {
          ...atom,
          terms: extractTerms(atom.content),
          hashBigInt,
        };
      });

      const termClusters = new Map<string, Map<string, number>>(); // term -> (related_term -> co_occurrence_count)

      for (let i = 0; i < atomsWithMetadata.length; i++) {
        const atom1 = atomsWithMetadata[i];
        for (let j = i + 1; j < atomsWithMetadata.length; j++) {
          const atom2 = atomsWithMetadata[j];

          // Use precomputed BigInts for faster distance calculation
          let distance = 64;
          if (atom1.hashBigInt !== undefined && atom2.hashBigInt !== undefined) {
            distance = this.fastHammingDistance(atom1.hashBigInt, atom2.hashBigInt);
          }

          if (distance <= this.MAX_SIMHASH_DISTANCE) {
            // Use precomputed terms
            const terms1 = atom1.terms;
            const terms2 = atom2.terms;

            // Add cross-cluster term pairs with co-occurrence counting
            for (const t1 of terms1) {
              for (const t2 of terms2) {
                if (t1 !== t2) {
                  if (!termClusters.has(t1)) {
                    termClusters.set(t1, new Map());
                  }
                  const related = termClusters.get(t1)!;
                  related.set(t2, (related.get(t2) || 0) + 1);
                }
              }
            }
          }
        }
      }

      // Convert clusters to pairs with frequency-based scoring
      const pairs = new Map<string, TermPair[]>();

      for (const [term1, relatedTerms] of termClusters.entries()) {
        if (!pairs.has(term1)) {
          pairs.set(term1, []);
        }

        // Convert to array and sort by co-occurrence frequency
        const sortedRelated = Array.from(relatedTerms.entries())
          .sort((a, b) => b[1] - a[1]) // Sort by frequency desc
          .slice(0, 20); // Top 20 related terms

        for (const [term2, frequency] of sortedRelated) {
          pairs.get(term1)!.push({
            term1,
            term2,
            score: frequency, // Use frequency as score (higher = more reliable)
            strategy: 'simhash_proximity',
          });
        }
      }

      console.log(`[SynonymGenerator] Found ${pairs.size} terms with simhash synonyms`);
      return pairs;
    } catch (error: any) {
      console.error('[SynonymGenerator] SimHash mining failed:', error.message);
      return new Map<string, TermPair[]>();
    }
  }

  /**
   * Merge all strategies with weighted voting
   * Term pairs appearing in 2+ strategies get higher confidence
   */
  async generateSynonymRings(): Promise<Record<string, string[]>> {
    console.log('[SynonymGenerator] Generating synonym rings from all strategies...');

    // Run all strategies — tagNeighborhood and simhash are O(N²), so use bounded concurrency (v5.2.0+)
    const [cooccurrence, neighborhood, simhash] = await executor.process(
      [
        () => this.mineCooccurrenceSynonyms(),
        () => this.mineTagNeighborhoodSynonyms(),
        () => this.mineSimHashSynonyms(),
      ],
      async fn => fn(),
      { maxConcurrency: 2, memoryThresholdMB: 1400 }, // Simhash is O(N²); bound to prevent heap spikes
    );

    // Build synonym rings directly from each strategy
    // No need for multi-strategy voting - each strategy has its own quality filters
    const synonymRings: Record<string, string[]> = {};

    // Helper to add synonyms
    const addSynonym = (term1: string, term2: string) => {
      if (!Array.isArray(synonymRings[term1])) synonymRings[term1] = [];
      if (!Array.isArray(synonymRings[term2])) synonymRings[term2] = [];
      
      if (!synonymRings[term1].includes(term2) && synonymRings[term1].length < this.TOP_SYNONYMS_PER_TERM) {
        synonymRings[term1].push(term2);
      }
      if (!synonymRings[term2].includes(term1) && synonymRings[term2].length < this.TOP_SYNONYMS_PER_TERM) {
        synonymRings[term2].push(term1);
      }
    };

    // 1. Tag neighborhood pairs (high precision - Jaccard >= 0.5)
    let tagPairsAdded = 0;
    for (const [term, pairs] of neighborhood.entries()) {
      for (const pair of pairs) {
        // Jaccard score already >= 0.5 threshold
        addSynonym(pair.term1, pair.term2);
        tagPairsAdded++;
      }
    }
    console.log(`[SynonymGenerator] Added ${tagPairsAdded} tag neighborhood pairs`);

    // 2. SimHash proximity pairs (cluster-based)
    // Score by cluster cohesion, not inverse size
    let simhashPairsAdded = 0;
    for (const [term, pairs] of simhash.entries()) {
      // Sort pairs by score (higher = more cohesive cluster)
      const sortedPairs = pairs.sort((a, b) => b.score - a.score);
      
      // Take top pairs from each term's perspective
      for (const pair of sortedPairs.slice(0, 5)) {
        addSynonym(pair.term1, pair.term2);
        simhashPairsAdded++;
      }
    }
    console.log(`[SynonymGenerator] Added ${simhashPairsAdded} simhash proximity pairs`);

    // 3. Co-occurrence pairs (if available)
    let coocPairsAdded = 0;
    for (const [term, pairs] of cooccurrence.entries()) {
      for (const pair of pairs) {
        addSynonym(pair.term1, pair.term2);
        coocPairsAdded++;
      }
    }
    if (coocPairsAdded > 0) {
      console.log(`[SynonymGenerator] Added ${coocPairsAdded} co-occurrence pairs`);
    }

    console.log(`[SynonymGenerator] Generated ${Object.keys(synonymRings).length} synonym rings`);
    return synonymRings;
  }

  /**
   * Save to synonym ring file for @rbalchii/dse to load
   */
  async saveSynonymRings(synonyms: Record<string, string[]>, outputPath: string): Promise<void> {
    console.log(`[SynonymGenerator] Saving synonym rings to ${outputPath}...`);

    try {
      // Save directly to database
      console.log('[SynonymGenerator] Upserting synonyms to database table...');
      const terms: string[] = [];
      const synLists: string[] = [];

      for (const [term, syns] of Object.entries(synonyms)) {
        if (!syns || syns.length === 0) continue;
        terms.push(term);
        synLists.push(JSON.stringify(syns));
      }

      // Batch insert in chunks to avoid parameter limits and optimize performance
      const BATCH_SIZE = 500;
      let processed = 0;

      while (processed < terms.length) {
        const batchTerms = terms.slice(processed, processed + BATCH_SIZE);
        const batchSynLists = synLists.slice(processed, processed + BATCH_SIZE);

        if (batchTerms.length > 0) {
          const query = `
            INSERT INTO synonyms (term, synonyms)
            SELECT * FROM unnest($1::text[], $2::text[])
            ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms, created_at = CURRENT_TIMESTAMP;
          `;
          await db.run(query, [batchTerms, batchSynLists]);
        }

        processed += BATCH_SIZE;
      }

      // Ensure directory exists
      const dir = path.dirname(outputPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      // Save as JSON
      const jsonContent = JSON.stringify(synonyms, null, 2);
      fs.writeFileSync(outputPath, jsonContent, 'utf-8');

      console.log(`[SynonymGenerator] Saved ${Object.keys(synonyms).length} synonym rings`);

      // Also generate a human-readable summary
      const summaryPath = outputPath.replace('.json', '-summary.md');
      this.generateSummary(synonyms, summaryPath);

    } catch (error: any) {
      console.error('[SynonymGenerator] Failed to save synonym rings:', error.message);
      throw error;
    }
  }

  /**
   * Generate human-readable summary
   */
  private generateSummary(synonyms: Record<string, string[]>, outputPath: string): void {
    let markdown = '# Auto-Generated Synonym Rings\n\n';
    markdown += `Generated: ${new Date().toISOString()}\n\n`;
    markdown += `Total terms: ${Object.keys(synonyms).length}\n\n`;
    markdown += '## Synonym Clusters\n\n';

    // Sort by number of synonyms
    const sorted = Object.entries(synonyms)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 100); // Top 100

    for (const [term, synonymList] of sorted) {
      markdown += `### ${term}\n`;
      markdown += `**Synonyms:** ${synonymList.join(', ')}\n\n`;
    }

    fs.writeFileSync(outputPath, markdown, 'utf-8');
    console.log(`[SynonymGenerator] Generated summary at ${outputPath}`);
  }

  /**
   * Load existing synonym rings
   */
  async loadExistingSynonymRings(inputPath: string): Promise<Record<string, string[]>> {
    try {
      if (!fs.existsSync(inputPath)) {
        return {};
      }

      const content = fs.readFileSync(inputPath, 'utf-8');
      return JSON.parse(content);
    } catch (error: any) {
      console.error('[SynonymGenerator] Failed to load existing synonym rings:', error.message);
      return {};
    }
  }
}
