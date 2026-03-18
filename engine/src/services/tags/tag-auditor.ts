/**
 * Tag Quality Auditor
 * 
 * Analyzes tagging patterns to identify:
 * 1. Under-tagged atoms (high content, few tags)
 * 2. Over-tagged atoms (noise)
 * 3. Orphan tags (used once, never retrieved)
 * 4. Tag clusters (tags that always appear together)
 * 5. Missing tags (common terms not used as tags)
 * 
 * Usage:
 *   const auditor = new TagAuditor();
 *   const report = await auditor.generateAuditReport();
 *   console.log(report);
 */

import { db } from '../../core/db.js';
import { nlp } from '../search/query-parser.js';

interface AuditReport {
  totalAtoms: number;
  totalTags: number;
  underTagged: UnderTaggedAtom[];
  orphanTags: string[];
  tagClusters: string[][];
  suggestions: TagSuggestion[];
  statistics: TagStatistics;
}

interface UnderTaggedAtom {
  id: string;
  source: string;
  contentLength: number;
  tagCount: number;
  suggestedTags: string[];
}

interface TagSuggestion {
  atomId: string;
  suggestedTags: string[];
  confidence: number;
}

interface TagStatistics {
  avgTagsPerAtom: number;
  medianTagsPerAtom: number;
  maxTagsInAtom: number;
  uniqueTags: number;
  tagsUsedOnce: number;
}

export class TagAuditor {
  /**
   * Find under-tagged content
   */
  async findUnderTaggedAtoms(minContentLength: number = 500, maxTags: number = 2): Promise<UnderTaggedAtom[]> {
    console.log('[TagAuditor] Finding under-tagged atoms...');
    
    // Fetch all existing distinct tags once for performance
    // Bolt: Optimized array unnesting using implicit lateral join
    const allTagsQuery = `SELECT DISTINCT tag FROM atoms, unnest(tags) as tag WHERE tags IS NOT NULL`;
    const allTagsResult = await db.run(allTagsQuery);
    const allTags = allTagsResult.rows
      ? (allTagsResult.rows as any[])
          .map((r: any) => r.tag)
          .filter((tag: string) => tag && tag.length > 0)
      : [];

    const query = `
      SELECT id, source_path, content, length(content) as content_length,
             cardinality(tags) as tag_count, tags
      FROM atoms
      WHERE length(content) > $1 
        AND (tags IS NULL OR cardinality(tags) < $2)
      ORDER BY length(content) DESC
      LIMIT 100
    `;
    
    const result = await db.run(query, [minContentLength, maxTags]);
    
    if (!result.rows) return [];
    
    const underTagged: UnderTaggedAtom[] = [];
    
    for (const row of result.rows as any[]) {
      const suggestedTags = await this.suggestTagsForAtom(row.id, 5, {
        content: row.content || '',
        existingTags: row.tags || [],
        allTags
      });
      
      underTagged.push({
        id: row.id,
        source: row.source_path,
        contentLength: row.content_length,
        tagCount: row.tag_count || 0,
        suggestedTags
      });
    }
    
    console.log(`[TagAuditor] Found ${underTagged.length} under-tagged atoms`);
    return underTagged;
  }

  /**
   * Find orphan tags (used only once)
   */
  async findOrphanTags(minAtoms: number = 100): Promise<string[]> {
    console.log('[TagAuditor] Finding orphan tags...');
    
    // Bolt: Optimized array unnesting using implicit lateral join to prevent materializing intermediate table
    const query = `
      SELECT tag, COUNT(*) as usage_count
      FROM atoms, unnest(tags) as tag
      WHERE tags IS NOT NULL
      GROUP BY tag
      HAVING COUNT(*) = 1
      ORDER BY tag
    `;
    
    const result = await db.run(query);
    
    if (!result.rows) return [];
    
    const orphanTags = (result.rows as any[])
      .map((r: any) => r.tag)
      .filter((tag: string) => tag && tag.length > 0);
    
    console.log(`[TagAuditor] Found ${orphanTags.length} orphan tags`);
    return orphanTags;
  }

  /**
   * Find tag clusters (tags that always appear together)
   */
  async findTagClusters(minSupport: number = 10): Promise<string[][]> {
    console.log('[TagAuditor] Finding tag clusters...');
    
    // Bolt: Optimized array unnesting using CTE to avoid duplicate unnest() execution
    const query = `
      WITH atom_tags AS (
        SELECT id, tag
        FROM atoms, unnest(tags) as tag
        WHERE tags IS NOT NULL
      ),
      tag_pairs AS (
        SELECT 
          t1.tag as tag1,
          t2.tag as tag2,
          COUNT(*) as co_occurrence
        FROM atom_tags t1
        JOIN atom_tags t2 ON t1.id = t2.id AND t1.tag < t2.tag
        GROUP BY t1.tag, t2.tag
        HAVING COUNT(*) >= $1
      )
      SELECT tag1, tag2, co_occurrence
      FROM tag_pairs
      ORDER BY co_occurrence DESC
      LIMIT 100
    `;
    
    const result = await db.run(query, [minSupport]);
    
    if (!result.rows) return [];
    
    // Build clusters from pairs
    const clusters = new Map<string, Set<string>>();
    
    for (const row of result.rows as any[]) {
      const { tag1, tag2 } = row;
      
      if (!clusters.has(tag1)) {
        clusters.set(tag1, new Set());
      }
      clusters.get(tag1)!.add(tag2);
      
      if (!clusters.has(tag2)) {
        clusters.set(tag2, new Set());
      }
      clusters.get(tag2)!.add(tag1);
    }
    
    // Convert to array of clusters
    const clusterArray: string[][] = [];
    const processed = new Set<string>();
    
    for (const [seed, members] of clusters.entries()) {
      if (processed.has(seed)) continue;
      
      const cluster = [seed, ...Array.from(members)];
      clusterArray.push(cluster);
      
      for (const member of members) {
        processed.add(member);
      }
    }
    
    console.log(`[TagAuditor] Found ${clusterArray.length} tag clusters`);
    return clusterArray;
  }

  /**
   * Suggest tags for an atom based on content
   */
  async suggestTagsForAtom(
    atomId: string,
    limit: number = 5,
    context?: { content: string; existingTags: string[]; allTags: string[] }
  ): Promise<string[]> {
    try {
      let atomContent = '';
      let existingTags: Set<string>;
      let allTags: string[];

      if (context) {
        atomContent = context.content;
        existingTags = new Set(context.existingTags || []);
        allTags = context.allTags;
      } else {
        // Get atom content
        const atomQuery = `SELECT content, tags FROM atoms WHERE id = $1`;
        const atomResult = await db.run(atomQuery, [atomId]);

        if (!atomResult.rows || atomResult.rows.length === 0) {
          return [];
        }

        const atom = atomResult.rows[0] as any;
        atomContent = atom.content || '';
        existingTags = new Set(atom.tags || []);

        // Get all existing tags
        // Bolt: Optimized array unnesting using implicit lateral join
        const allTagsQuery = `SELECT DISTINCT tag FROM atoms, unnest(tags) as tag WHERE tags IS NOT NULL`;
        const allTagsResult = await db.run(allTagsQuery);

        if (!allTagsResult.rows) return [];

        allTags = (allTagsResult.rows as any[])
          .map((r: any) => r.tag)
          .filter((tag: string) => tag && tag.length > 0);
      }
      
      // Extract key terms from content
      const doc = nlp.readDoc(atomContent);
      const terms = doc.tokens()
        .filter((t: any) => {
          const pos = t.out(nlp.its.pos);
          return pos === 'NOUN' || pos === 'PROPN' || pos === 'ADJ';
        })
        .out(nlp.its.normal)
        .filter((term: string) => term.length > 3 && term.length < 30)
        .slice(0, 20);
      
      // Find matching tags
      const suggestions = terms.filter((term: string) => {
        const termLower = term.toLowerCase();
        return allTags.some(tag => 
          tag.toLowerCase() === termLower || 
          tag.toLowerCase().includes(termLower)
        ) && !existingTags.has(term);
      }).slice(0, limit);
      
      return suggestions;
    } catch (error: any) {
      console.error('[TagAuditor] Failed to suggest tags:', error.message);
      return [];
    }
  }

  /**
   * Get tag statistics
   */
  async getTagStatistics(): Promise<TagStatistics> {
    const query = `
      SELECT 
        COUNT(*) as total_atoms,
        AVG(COALESCE(cardinality(tags), 0)) as avg_tags,
        MAX(COALESCE(cardinality(tags), 0)) as max_tags,
        COUNT(DISTINCT unnest(tags)) as unique_tags
      FROM atoms
    `;
    
    const result = await db.run(query);
    
    if (!result.rows || result.rows.length === 0) {
      return {
        avgTagsPerAtom: 0,
        medianTagsPerAtom: 0,
        maxTagsInAtom: 0,
        uniqueTags: 0,
        tagsUsedOnce: 0
      };
    }
    
    const row = result.rows[0] as any;
    
    // Get tags used once
    // Bolt: Optimized array unnesting using implicit lateral join
    const orphanQuery = `
      SELECT COUNT(*) as count
      FROM (
        SELECT tag
        FROM atoms, unnest(tags) as tag
        WHERE tags IS NOT NULL
        GROUP BY tag
        HAVING COUNT(*) = 1
      )
    `;
    
    const orphanResult = await db.run(orphanQuery);
    const tagsUsedOnce = orphanResult.rows?.[0]?.count || 0;
    
    return {
      avgTagsPerAtom: parseFloat(row.avg_tags) || 0,
      medianTagsPerAtom: Math.round(parseFloat(row.avg_tags) || 0), // Approximation
      maxTagsInAtom: row.max_tags || 0,
      uniqueTags: row.unique_tags || 0,
      tagsUsedOnce
    };
  }

  /**
   * Generate comprehensive audit report
   */
  async generateAuditReport(): Promise<AuditReport> {
    console.log('[TagAuditor] Generating comprehensive audit report...');
    
    const [
      totalAtoms,
      totalTags,
      underTagged,
      orphanTags,
      tagClusters,
      statistics
    ] = await Promise.all([
      this.getTotalAtoms(),
      this.getTotalTags(),
      this.findUnderTaggedAtoms(),
      this.findOrphanTags(),
      this.findTagClusters(5),
      this.getTagStatistics()
    ]);
    
    const suggestions: TagSuggestion[] = underTagged.map(atom => ({
      atomId: atom.id,
      suggestedTags: atom.suggestedTags,
      confidence: atom.suggestedTags.length > 0 ? 0.8 : 0.3
    }));
    
    return {
      totalAtoms,
      totalTags,
      underTagged,
      orphanTags,
      tagClusters,
      suggestions,
      statistics
    };
  }

  private async getTotalAtoms(): Promise<number> {
    const result = await db.run('SELECT COUNT(*) as count FROM atoms');
    return result.rows?.[0]?.count || 0;
  }

  private async getTotalTags(): Promise<number> {
    // Bolt: Optimized array unnesting using implicit lateral join
    const result = await db.run('SELECT COUNT(DISTINCT tag) as count FROM atoms, unnest(tags) as tag WHERE tags IS NOT NULL');
    return result.rows?.[0]?.count || 0;
  }
}
