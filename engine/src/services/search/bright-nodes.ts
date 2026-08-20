/**
 * Bright Node Protocol — "The Illuminator"
 *
 * Selective Graph Illumination for reasoning models.
 * Implements the "Bright Node" inference protocol where only relevant
 * graph nodes are illuminated for reasoning, similar to how a flashlight
 * illuminates only the relevant parts of a dark room.
 *
 * This supports the "Logic-Data Decoupling" concept by providing
 * structured graph data to lightweight reasoning models.
 *
 * Extracted from search.ts for clean separation of the graph reasoning layer.
 */

import { config } from '../../config/index.js';
import type { SearchResult } from './search-utils.js';
import { executeSearch } from './search.js';
import { getSetting } from '../settings.js';

export interface BrightNode {
    id: string;
    content: string;
    source: string;
    timestamp: number;
    buckets: string[];
    tags: string[];
    epochs: string;
    provenance: string;
    score: number;
    sequence?: number;
    molecular_signature?: string;
    relationships: BrightNodeRelationship[];
}

export interface BrightNodeRelationship {
    targetId: string;
    relationshipType: string;
    strength: number;
}

/**
 * Get bright node settings from database (v5.2.0+)
 */
async function getBrightNodeSettings() {
  const [maxCharsLimit, ftsWindowSize] = await Promise.all([
    getSetting('search.max_chars_limit', 1048576),
    getSetting('search.fts_window_size', 3),
  ]);

  return {
    MAX_CHARS_LIMIT: maxCharsLimit ?? 1048576,
    FTS_WINDOW_SIZE: ftsWindowSize ?? 3,
  };
}

export async function getBrightNodes(
    query: string,
    buckets: string[] = [],
    maxNodes?: number,
): Promise<BrightNode[]> {
  const settings = await getBrightNodeSettings();
  const resolvedMaxNodes = maxNodes ?? (settings.MAX_CHARS_LIMIT / 1024); // Default: ~1024 nodes from default limit

  console.log(`[BrightNode] Illuminating graph for query: "${query}"`);

  // First, get relevant search results using the enhanced Tag-Walker (via executeSearch)
  const { results: searchResults } = await executeSearch(query, buckets, resolvedMaxNodes * settings.FTS_WINDOW_SIZE, 'all');

    if (searchResults.length === 0) {
        console.log('[BrightNode] No results found for query.');
        return [];
    }

    // Take top results based on score
    const topResults = searchResults
        .sort((a, b) => b.score - a.score)
        .slice(0, maxNodes);

    // Create bright nodes with relationship information
    const brightNodes: BrightNode[] = topResults.map(result => ({
        id: result.id,
        content: result.content,
        source: result.source,
        timestamp: result.timestamp,
        buckets: result.buckets,
        tags: result.tags,
        epochs: result.epochs,
        provenance: result.provenance,
        score: result.score,
        sequence: result.sequence, // Pass through sequence
        molecular_signature: result.molecular_signature,   // V4 Nomenclature
        relationships: [], // Will be populated based on shared tags/buckets
    }));

    // Identify relationships between nodes based on shared attributes
    for (let i = 0; i < brightNodes.length; i++) {
        const currentNode = brightNodes[i];
        const relationships: BrightNodeRelationship[] = [];

        for (let j = 0; j < brightNodes.length; j++) {
            if (i === j) continue;

            const otherNode = brightNodes[j];
            let relationshipStrength = 0;
            let relationshipType = 'related';

            // 1. Semantic Overlap (Tags & Buckets)
            const sharedBuckets = currentNode.buckets.filter((b: string) => otherNode.buckets.includes(b));
            const sharedTags = currentNode.tags.filter((t: string) => otherNode.tags.includes(t));
            relationshipStrength += sharedBuckets.length * 2 + sharedTags.length;

            // 2. Source Continuity (Same Document)
            if (currentNode.source === otherNode.source) {
                relationshipStrength += 5; // Strong boost for same file
                relationshipType = 'same_source';

                // 3. Sequential Adjacency (The "Markov Link")
                if (currentNode.sequence !== undefined && otherNode.sequence !== undefined) {
                    const dist = Math.abs(currentNode.sequence - otherNode.sequence);
                    if (dist === 1) {
                        relationshipStrength += 10; // Massive boost for direct neighbors
                        relationshipType = 'next_chunk';
                    } else if (dist < 5) {
                        relationshipStrength += 3; // Boost for nearby chunks
                    }
                }
            }

            if (relationshipStrength > 0) {
                relationships.push({
                    targetId: otherNode.id,
                    relationshipType,
                    strength: relationshipStrength,
                });
            }
        }

        // Sort relationships by strength and keep top 5
        currentNode.relationships = relationships
            .sort((a, b) => b.strength - a.strength)
            .slice(0, 5);
    }

    console.log(`[BrightNode] Illuminated ${brightNodes.length} nodes with relationships`);

    return brightNodes;
}

/**
 * Get Structured Graph for Reasoning Models
 *
 * Formats the bright nodes into a structure suitable for reasoning models
 * as described in the "Logic-Data Decoupling" section of the white paper.
 */
export async function getStructuredGraph(
    query: string,
    buckets: string[] = [],
): Promise<any> {
    const brightNodes = await getBrightNodes(query, buckets);

    // Format as a graph structure suitable for reasoning models
    return {
        nodes: brightNodes.map(node => ({
            id: node.id,
            content: node.content.substring(0, 500), // Truncate for efficiency
            tags: node.tags,
            buckets: node.buckets,
            provenance: node.provenance,
            score: node.score,
        })),
        edges: brightNodes.flatMap(node =>
            node.relationships.map(rel => ({
                source: node.id,
                target: rel.targetId,
                type: rel.relationshipType,
                strength: rel.strength,
            })),
        ),
        query: query,
        timestamp: Date.now(),
    };
}
