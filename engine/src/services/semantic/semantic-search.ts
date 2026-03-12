
/**
 * Semantic Search Integration for ECE (Semantic Shift Architecture)
 * 
 * Provides a bridge between the new semantic search functionality and the existing search API
 * ensuring backward compatibility while enabling enhanced relationship-focused search.
 */

import { db } from '../../core/db.js';
import { vector } from '../../core/vector.js';
import { NlpService } from '../nlp/nlp-service.js';
import { SemanticCategory } from '../../types/taxonomy.js';
import { parseNaturalLanguage, expandQuery } from '../nlp/query-parser.js';
import { ContextInflator } from '../search/context-inflator.js';
import { distributeQueryBudget, getBudgetForTerm, getAllTerms } from '../search/distributed-query.js';


interface SearchResult {
  id: string;
  content: string;
  source: string;
  timestamp: number;
  buckets: string[];
  tags: string[];
  epochs: string;
  provenance: string;
  score: number;
  molecular_signature?: string;
  semanticCategories?: SemanticCategory[];
  relatedEntities?: string[];
  // Inflation fields
  compound_id?: string;
  start_byte?: number;
  end_byte?: number;
  is_inflated?: boolean;
}

export async function executeSemanticSearch(
  query: string,
  buckets?: string[],
  maxChars: number = 5242,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  explicitTags: string[] = [],
  codeWeight: number = 1.0 // 1.0 = normal, 0.1 = heavily penalized
): Promise<{
  context: string;
  results: SearchResult[];
  toAgentString: () => string;
  strategy?: string;
  splitQueries?: string[];
  metadata?: any;
}> {

  console.log(`[SemanticSearch] executeSemanticSearch called with query: "${query}", provenance: ${provenance}`);

  // Extract potential entities from the query
  const queryEntities = extractEntitiesFromQuery(query);
  const scopeTags = [...explicitTags];

  // Parse the query for natural language elements
  // Sanitize for FTS: Remove punctuation that causes syntax errors (like ?)
  const parsedQuery = parseNaturalLanguage(query).replace(/[?*:|!<>(){}[\]^"~]/g, ' ');
  const expansionTags = await expandQuery(parsedQuery);
  const searchTerms = [...new Set([...parsedQuery.split(/\s+/), ...expansionTags])];

  // Detect potential entity pairs for relationship search
  const entityPairs: string[] = [];
  if (searchTerms.length >= 2) {
    // Look for relationship indicators in the search terms
    const relationshipIndicators = ['and', 'with', 'met', 'told', 'said', 'visited', 'called', 'texted', 'about', 'relationship'];
    for (let i = 0; i < searchTerms.length - 1; i++) {
      if (relationshipIndicators.includes(searchTerms[i].toLowerCase())) {
        // Found a potential relationship: [person1] [indicator] [person2]
        if (i > 0 && i < searchTerms.length - 1) {
          entityPairs.push(`${searchTerms[i - 1]}_${searchTerms[i + 1]}`);
          entityPairs.push(`${searchTerms[i + 1]}_${searchTerms[i - 1]}`); // Bidirectional
        }
      }
    }
  }

  // 0. Perform Vector Search (Hybrid Retrieval)
  // ---------------------------------------------------------------------------
  let vectorIds: number[] = [];
  const vectorScores = new Map<number, number>(); // vector_id -> similarity (0..1)

  try {
    // Lazy init vector if needed
    if (!vector.isInitialized) await vector.init();

    // Generate embedding for query
    const nlpService = new NlpService();
    // Use the parsed query to avoid noise, or original query? Original is usually better for embeddings.
    const embedding = await nlpService.getEmbedding(query);

    // Search Index
    const vectorResults = vector.search(embedding, 50); // Get top 50 vector matches
    vectorIds = vectorResults.ids;

    // Store scores for merging
    vectorResults.ids.forEach((id, index) => {
      const distance = vectorResults.distances[index];
      // Convert distance to similarity score (Approximate, assuming cosine distance 0..2)
      // 0 distance = 1.0 score. 1.0 distance = 0.0 score.
      // Usually Cosine Similarity = 1 - Cosine Distance
      const similarity = Math.max(0, 1.0 - distance);
      vectorScores.set(id, similarity);
    });

    if (vectorIds.length > 0) {
      console.log(`[SemanticSearch] Vector Index returned ${vectorIds.length} hits.`);
    }
  } catch (e) {
    console.warn(`[SemanticSearch] Vector search failed, falling back to pure FTS.`, e);
  }


  // Build the search query to find semantic molecules using proper SQL FTS syntax
  // Updated to include molecular coordinates from molecules table for Context Inflation
  // Use OR-based logic (|) on filtered keywords to allow conversational queries ("fuzzy" match)
  const tsQueryString = searchTerms.filter(t => t.trim().length > 0).join(' | ');

  // Build query with correct parameter indexes
  // NOTE: We do NOT select a.content to prevent fetching massive blobs.
  // Content is read from disk using coordinates during ContextInflation.
  const sqlParams: any[] = [tsQueryString]; // $1 = tsquery
  
  let vectorClause = '';
  if (vectorIds.length > 0) {
    // $2 = vector_ids array
    vectorClause = ` OR a.vector_id = ANY($2)`;
    sqlParams.push(vectorIds);
  }

  let paramIndex = vectorIds.length > 0 ? 2 : 1;
  const filterClauses: string[] = [];

  // Provenance filter
  if (provenance !== 'all') {
    paramIndex++;
    filterClauses.push(`a.provenance = $${paramIndex}`);
    sqlParams.push(provenance);
  }

  // Bucket filter
  if (buckets && buckets.length > 0) {
    paramIndex++;
    filterClauses.push(`EXISTS(SELECT 1 FROM unnest(a.buckets) as bucket WHERE bucket = ANY($${paramIndex}))`);
    sqlParams.push(buckets);
  }

  // Tag filter
  if (scopeTags.length > 0) {
    paramIndex++;
    filterClauses.push(`EXISTS(SELECT 1 FROM unnest(a.tags) as tag WHERE tag = ANY($${paramIndex}))`);
    sqlParams.push(scopeTags);
  }

  // Build WHERE clause
  const whereParts = [`(to_tsvector('simple', a.content) @@ to_tsquery('simple', $1)${vectorClause})`];
  if (filterClauses.length > 0) {
    whereParts.push(filterClauses.join(' AND '));
  }

  const searchQuery = `
    SELECT a.id, a.source_path as source, a.timestamp, a.buckets, a.tags, a.epochs, a.provenance, a.simhash,
           0 as score,
           COALESCE(m.compound_id, a.compound_id) as compound_id,
           COALESCE(m.start_byte, a.start_byte) as start_byte,
           COALESCE(m.end_byte, a.end_byte) as end_byte,
           a.vector_id
      FROM atoms a
      LEFT JOIN molecules m ON a.id = m.id
      WHERE ${whereParts.join(' AND ')}
      ORDER BY timestamp DESC
      LIMIT 50
  `;

  try {
    const result = await db.run(searchQuery, sqlParams);
    const rows = result.rows || [];

    // Process results and apply semantic scoring
    const processedResults: SearchResult[] = [];

    for (const row of rows) {
      const id = String(row.id || '');
      const source = String(row.source || '');
      const startByte = typeof row.start_byte === 'number' ? row.start_byte : Number(row.start_byte);
      const endByte = typeof row.end_byte === 'number' ? row.end_byte : Number(row.end_byte);
      const rowVectorId = typeof row.vector_id === 'number' ? row.vector_id : Number(row.vector_id || 0);

      const rowBuckets = Array.isArray(row.buckets) ? row.buckets as string[] : (typeof row.buckets === 'string' ? [row.buckets] : []);
      const rowTags = Array.isArray(row.tags) ? row.tags as string[] : (typeof row.tags === 'string' ? [row.tags] : []);

      // Fetch content for scoring (not stored, just for relevance calculation)
      let content = '';
      let contentForScoring = '';
      try {
        if (source && source.startsWith('/') && startByte >= 0 && endByte > startByte) {
          // Read content from disk for scoring
          const fs = await import('fs');
          const fullContent = fs.readFileSync(source, 'utf-8');
          contentForScoring = fullContent.substring(startByte, endByte);
          content = contentForScoring; // Store for result
        }
      } catch (e) {
        // File read failed, content remains empty - scoring will be based on vector only
        console.debug(`[SemanticSearch] Could not read content for scoring: ${source}`);
      }

      // Calculate semantic relevance score using actual content
      let semanticScore = calculateSemanticScore(contentForScoring, queryEntities, searchTerms, entityPairs);

      // Calculate Vector Score
      let vectorScore = 0;
      if (rowVectorId && vectorScores.has(rowVectorId)) {
        vectorScore = (vectorScores.get(rowVectorId) || 0) * 100; // Scale 0..1 to 0..100
      }

      // Hybrid Merge Strategy: Max(Semantic, Vector) + Boost if match both
      let score = Math.max(semanticScore, vectorScore);
      if (semanticScore > 0 && vectorScore > 0) {
        score += (Math.min(semanticScore, vectorScore) * 0.5); // Boost if confirmed by both methods
      }

      // Apply provenance boost
      if (provenance === 'internal' && String(row[6] || '') === 'internal') {
        score *= 2.0;
      } else if (provenance === 'external' && String(row[6] || '') !== 'internal') {
        score *= 1.5;
      }

      // Apply Code/Log Weighting
      // If codeWeight is low < 1.0, penalize items that look like code or logs
      if (codeWeight < 1.0) {
        // Tag matching: DB stores 'Code', 'Log' (no hash). We check for various forms.
        const isCodeOrLog = rowTags.some(t => {
          const lower = t.toLowerCase().replace('#', '');
          return ['code', 'log', 'json', 'config', 'test'].includes(lower);
        });

        if (isCodeOrLog) {
          score *= codeWeight;
        }
      }

      // Check for relationship patterns in the content
      const relationshipEntities = findEntityPairs(content, queryEntities);
      const semanticCategories = determineSemanticCategories(content, relationshipEntities);

      // Create result object with proper structure
      const searchResult: SearchResult = {
        id: id,
        content: content,
        source: source,
        timestamp: typeof row[2] === 'number' ? row[2] : Date.now(),
        buckets: rowBuckets,
        tags: rowTags,
        epochs: String(row[5] || ''),
        provenance: String(row[6] || ''),
        molecular_signature: String(row[7] || ''),
        score: typeof row[8] === 'number' ? row[8] : 0,
        semanticCategories,
        relatedEntities: relationshipEntities.length > 0 ? relationshipEntities : undefined,
        // Inflation Metadata
        compound_id: String(row[9] || ''),
        start_byte: startByte,
        end_byte: endByte
      };

      processedResults.push(searchResult);
    }

    // Sort by score descending (before inflation merge)
    processedResults.sort((a, b) => (b.score || 0) - (a.score || 0));

    // --- CONTEXT INFLATION (Lazy Molecule Radial Inflation) ---
    // Use atom positions for radial expansion instead of compound body blobs
    console.log(`[SemanticSearch] Radially inflating from atom positions for ${searchTerms.length} terms...`);

    // Calculate dynamic radius based on budget and number of terms
    // Budget split: if 5 terms, each gets ~20% of the window
    const STOPWORDS = ['and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'about', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'am', 'working', 'talking', 'thinking', 'using', 'making'];
    const termsToInflate = searchTerms.filter(t => t.trim().length > 2 && !STOPWORDS.includes(t.toLowerCase())); // Skip tiny terms and stopwords

    console.log(`[SemanticSearch] Inflating terms: ${termsToInflate.join(', ')}`);

    // Radius should be maximize context if budget permits.
    // User request: "massive expansion", "1k words before and after" (~6000 chars radius).
    // Strategy: 
    // - If budget is high (>20k), target ~5-8 high-quality results per term.
    // - Cap radius at 6000 chars (approx 1k words).
    // - Ensure we don't exceed per-term budget share.

    // Budget per term
    const termBudget = maxChars / Math.max(1, termsToInflate.length);

    // Target ~8 results per term to allow sufficient breadth
    let radiusPerTerm = Math.floor(termBudget / 8);

    // Cap at 32000 (massive context) but allow it to be at least 150
    // This allows "just scale" behavior up to very large windows
    radiusPerTerm = Math.max(150, Math.min(32000, radiusPerTerm));

    // Calculate max results based on this radius to fill the budget
    // If radius is 6000 (12k diameter), and budget is 50k, we get ~4 results.
    const maxResultsPerTerm = Math.max(3, Math.floor(termBudget / (radiusPerTerm * 2)));

    console.log(`[SemanticSearch] Inflation Strategy: Radius=${radiusPerTerm} chars, MaxResults=${maxResultsPerTerm}/term`);

    // Collect radially inflated results for each search term
    let inflatedResults: SearchResult[] = [];
    const maxWindowSize = radiusPerTerm * 4; // Allow merging of up to 4 consecutive windows


    const inflationPromises = termsToInflate.map(term =>
      ContextInflator.inflateFromAtomPositions(
        term,
        radiusPerTerm,
        maxResultsPerTerm,
        maxWindowSize,
        { buckets, provenance } // Pass filters
      ).then(results => ({ term, results }))
    );

    const inflationResults = await Promise.all(inflationPromises);

    for (const { term, results: termResults } of inflationResults) {
      if (termResults.length > 0) {
        console.log(`[SemanticSearch] Term "${term}" inflated to ${termResults.length} results.`);
      }
      inflatedResults.push(...(termResults as unknown as SearchResult[]));
    }

    // --- INTERSECTION SCORING ---
    // Boost results that contain multiple unique query terms (Logical AND preference)
    if (termsToInflate.length > 1) {
      // Pre-calculate lowercased terms for performance
      const termsLower = termsToInflate.map(t => t.toLowerCase());

      for (const result of inflatedResults) {
        let termMatches = 0;
        const contentLower = (result.content || '').toLowerCase();

        for (const term of termsLower) {
          if (contentLower.includes(term)) {
            termMatches++;
          }
        }

        // Boost score: Base score + (Matches ^ 2 * 50)
        // 1 match = +50
        // 2 matches = +200
        // 3 matches = +450
        if (termMatches > 0) {
          result.score = (result.score || 0) + (Math.pow(termMatches, 2) * 50);
        }
      }

      // Re-sort based on new intersection scores
      inflatedResults.sort((a, b) => (b.score || 0) - (a.score || 0));
    }

    // If no radial results, fallback to old method with processedResults
    if (inflatedResults.length === 0 && processedResults.length > 0) {
      console.log(`[SemanticSearch] No atom positions found, falling back to compound inflation (Radius: ${radiusPerTerm})`);
      inflatedResults = await ContextInflator.inflate(processedResults, maxChars, radiusPerTerm);
    }

    console.log(`[SemanticSearch] Inflated into ${inflatedResults.length} windows.`);

    // Build context string from INFLATED results
    let totalChars = 0;
    let context = '';

    // Filter to token/char budget logic using inflated content
    const finalResults: SearchResult[] = [];

    for (const res of inflatedResults) {
      // Get content from the result - it should already have content from inflation or original
      let contentToUse = (res.content || '').trim();

      // Clean up "......" artifacts from empty inflation
      if (contentToUse === '......' || contentToUse === '...') contentToUse = '';

      if (contentToUse && contentToUse.length > 10) { // Require at least 10 meaningful chars
        let finalContent = contentToUse;
        const remainingBudget = maxChars - totalChars;

        if (remainingBudget <= 0) break; // Budget full

        // Truncate if too large for remaining budget
        if (finalContent.length > remainingBudget) {
          finalContent = finalContent.substring(0, remainingBudget) + '...';
        }

        context += `[Source: ${res.source || 'unknown'}](Timestamp: ${new Date(res.timestamp).toISOString()
          }) \n${finalContent} \n\n`;
        totalChars += finalContent.length;

        // Push modified result with truncated content
        finalResults.push({
          ...res,
          content: finalContent
        });
      }
    }

    console.log(`[SemanticSearch] Found ${finalResults.length} results with total ${totalChars} characters`);

    return {
      context,
      results: finalResults,
      toAgentString: () => {
        return finalResults.map(r => `[${r.source}] ${r.content} `).join('\n\n');
      },
      strategy: 'semantic_relationship',
      splitQueries: entityPairs,
      metadata: {
        query,
        queryEntities,
        entityPairs,
        resultsCount: finalResults.length,
        totalCharacters: totalChars,
        semanticCategories: [...new Set(finalResults.flatMap(r => r.semanticCategories || []))]
      }
    };
  } catch (error) {
    console.error('[SemanticSearch] Search error:', error);
    // Return empty results instead of throwing to prevent frontend crashes
    return {
      context: '',
      results: [],
      toAgentString: () => '',
      strategy: 'semantic_relationship',
      splitQueries: [],
      metadata: {
        query,
        queryEntities: [],
        entityPairs: [],
        resultsCount: 0,
        totalCharacters: 0,
        semanticCategories: []
      }
    };
  }
}

/**
 * Extract potential entities from a query string
 */
function extractEntitiesFromQuery(query: string): string[] {
  // Simple entity extraction - could be enhanced with NER
  const words = query.toLowerCase().split(/\s+/);
  const potentialEntities: string[] = [];

  // Look for capitalized words (potential names)
  const capitalizedWords = query.split(/\s+/).filter(word =>
    word.length > 1 && /^[A-Z]/.test(word) && !isCommonCapitalizedWord(word)
  );

  potentialEntities.push(...capitalizedWords);

  return [...new Set(potentialEntities)];
}

/**
 * Check if a word is a common capitalized word that's not likely an entity
 */
function isCommonCapitalizedWord(word: string): boolean {
  const commonWords = ['The', 'And', 'For', 'Are', 'Is', 'In', 'On', 'At', 'To', 'With', 'By', 'A', 'An', 'Of', 'As', 'The', 'This', 'That', 'These', 'Those', 'Have', 'Has', 'Had', 'Do', 'Does', 'Did', 'Will', 'Would', 'Could', 'Should', 'May', 'Might', 'Must', 'Can', 'Shall'];
  return commonWords.includes(word);
}

/**
 * Calculate semantic relevance score based on entity co-occurrence and relationship patterns
 */
function calculateSemanticScore(content: string, queryEntities: string[], searchTerms: string[], entityPairs: string[]): number {
  let score = 0;
  const contentLower = content.toLowerCase();

  // Boost for query term matches
  for (const term of searchTerms) {
    if (contentLower.includes(term.toLowerCase())) {
      score += 10;
    }
  }

  // Significant boost for entity pair relationships (relationship detection)
  for (const pair of entityPairs) {
    const [entity1, entity2] = pair.split('_');
    if (contentLower.includes(entity1.toLowerCase()) && contentLower.includes(entity2.toLowerCase())) {
      score += 100; // Strong boost for relationship content
    }
  }

  // Additional boost if content contains relationship indicators
  const relationshipIndicators = ['relationship', 'with', 'and', 'met', 'told', 'said', 'visited', 'called', 'texted', 'about', 'love', 'knows', 'friend', 'partner', 'couple', 'together'];
  for (const indicator of relationshipIndicators) {
    if (contentLower.includes(indicator)) {
      score += 5;
    }
  }

  // Boost for temporal indicators if looking for narratives
  const temporalIndicators = ['when', 'then', 'later', 'before', 'after', 'during', 'while', 'yesterday', 'today', 'tomorrow', 'morning', 'afternoon', 'evening', 'night'];
  for (const indicator of temporalIndicators) {
    if (contentLower.includes(indicator)) {
      score += 3;
    }
  }

  return score;
}

/**
 * Find pairs of entities that appear together in content
 */
function findEntityPairs(content: string, queryEntities: string[]): string[] {
  const contentLower = content.toLowerCase();
  const foundEntities = queryEntities.filter(entity =>
    contentLower.includes(entity.toLowerCase())
  );

  // Create pairs of entities found together
  const pairs: string[] = [];
  for (let i = 0; i < foundEntities.length; i++) {
    for (let j = i + 1; j < foundEntities.length; j++) {
      pairs.push(`${foundEntities[i]}_${foundEntities[j]} `);
      pairs.push(`${foundEntities[j]}_${foundEntities[i]} `); // Bidirectional
    }
  }

  return [...new Set(pairs)];
}

/**
 * Determine semantic categories based on content analysis
 */
function determineSemanticCategories(content: string, entityPairs: string[]): SemanticCategory[] {
  const categories: SemanticCategory[] = [];
  const contentLower = content.toLowerCase();

  // Check for relationship indicators
  if (entityPairs.length > 0 ||
    /relationship|friend|partner|love|met|told|said|visited|called|texted|together|dating|couple|family|wife|husband|girlfriend|boyfriend|with|and/.test(contentLower)) {
    categories.push(SemanticCategory.RELATIONSHIP);
  }

  // Check for narrative/story indicators
  if (/(when|then|later|before|after|during|while|first|next|finally|meanwhile|suddenly|story|remember|recall|yesterday|today|tomorrow|morning|afternoon|evening|night)/.test(contentLower)) {
    categories.push(SemanticCategory.NARRATIVE);
  }

  // Check for technical indicators
  if (/(function|class|method|variable|code|api|database|server|client|library|framework|module|component|system|architecture|node\.js|typescript|javascript)/.test(contentLower)) {
    categories.push(SemanticCategory.TECHNICAL);
  }

  // Check for location indicators
  if (/(in|at|near|by|city|town|country|state|street|avenue|road|building|home|office|address|albuquerque|bernalillo|sandia|los alamos|nm|tx|ca|ny|fl)/.test(contentLower)) {
    categories.push(SemanticCategory.LOCATION);
  }

  // Check for emotional indicators
  if (/(happy|sad|angry|excited|frustrated|anxious|joy|fear|love|hate|regret|hope|despair|grateful|felt|emotions|feelings|heart|soul|spirit)/.test(contentLower)) {
    categories.push(SemanticCategory.EMOTIONAL);
  }

  return categories;
}

/**
 * Distributed Radial Search (Lazy Molecule Architecture)
 * 
 * Uses 70/30 budget split:
 * - 70% for direct query atoms (evenly distributed)
 * - 30% for related/nearby atoms (5 per direct term)
 * 
 * Each atom is radially inflated from its byte position in compounds
 * to create virtual molecules on-the-fly.
 */
export async function executeDistributedRadialSearch(
  query: string,
  buckets?: string[], // Added parameter
  maxChars: number = 10000,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  codeWeight: number = 1.0
): Promise<{
  context: string;
  results: SearchResult[];
  toAgentString: () => string;
  metadata?: any;
}> {
  console.log(`[DistributedRadialSearch] Query: "${query}", Budget: ${maxChars} chars`);

  // 1. Distribute budget across terms
  const budget = await distributeQueryBudget(query, maxChars);
  // const allTerms = getAllTerms(budget); // Deprecated

  if (budget.directTerms.length === 0 && budget.relatedTerms.length === 0) {
    return {
      context: '',
      results: [],
      toAgentString: () => '',
      metadata: { query, termCount: 0, totalChars: 0 }
    };
  }

  // 2. Radially inflate from atom positions for each term
  // Dynamic radius: Scale with budget (Standard 085 Section 5.2)
  // Target: Up to 1k words (6000 chars) is standard, but scale to 32k if budget allows
  const expectedResults = 5; // Target fewer, larger chunks for deep context
  const directRadius = Math.max(500, Math.min(32000, Math.floor(maxChars / expectedResults / 2)));
  const relatedRadius = 300; // Increased broad context slightly

  console.log(`[DistributedRadialSearch] Radius Strategy: Direct=${directRadius}b (Deep), Related=${relatedRadius}b (Broad)`);

  const allResults: SearchResult[] = [];

  // 2. Elastic Context Strategy (Standard 087)
  // Instead of guessing a radius per term, we find ALL relevant atom positions first.
  // Then we divide the Global Budget by the Total Hits to determine the "Elastic Radius".
  // Few hits = Huge Context. Many hits = Focused Context.

  const allTerms = [...budget.directTerms, ...budget.relatedTerms];
  const termLocations = new Map<string, any[]>();
  let totalHits = 0;

  // Step 2a: Census - Find where these terms actually live
  console.log(`[ElasticContext] conducting census for terms: ${allTerms.map(t => t.term).join(', ')}`);

  for (const termObj of allTerms) {
    // Pass filters to census too, to avoid counting hits we will filter out anyway!
    const locations = await ContextInflator.getAtomLocations(
      termObj.term,
      50,
      { buckets, provenance }
    );
    if (locations.length > 0) {
      termLocations.set(termObj.term, locations);
      totalHits += locations.length;
    }
  }

  // Step 2b: Calculate Elastic Radius
  // Budget e.g. 50,000 chars. 
  // If 5 hits: 10,000 chars each (Huge).
  // If 50 hits: 1,000 chars each (focused).
  // If 0 hits: 0.
  const baseRadius = totalHits > 0 ? Math.floor(maxChars / totalHits / 2) : 0;

  // Clamp: Min 200 (readability), Max 32000 (sanity)
  const elasticRadius = Math.max(200, Math.min(32000, baseRadius));
  const maxResultPerTerm = 20; // Cap to avoid flooding

  console.log(`[ElasticContext] Census Results: ${totalHits} total hits. Elastic Radius = ${elasticRadius} bytes/hit`);

  // Step 2c: Inflate using the Elastic Radius
  // We can reuse the existing inflateFromAtomPositions but passing our calculated specific radius
  const processTerms = async (terms: any[], isRelated: boolean) => {
    // Parallelize term processing within the group
    const promises = terms.map(async (termObj) => {
      // Skip if no locations found (save the DB call)
      if (!termLocations.has(termObj.term)) return;

      const results = await ContextInflator.inflateFromAtomPositions(
        termObj.term,
        elasticRadius,
        maxResultPerTerm,
        elasticRadius * 4, // Allow merging up to 4x radius
        { buckets, provenance } // Pass filters
      );

      // Provenance is now handled in SQL, but we keep this as a safe backup or for consistency
      const filteredResults = provenance === 'all'
        ? results
        : results.filter(r => r.provenance === provenance);

      allResults.push(...filteredResults);
    });

    await Promise.all(promises);
  };

  // Parallelize processing of both direct and related terms
  await Promise.all([
    processTerms(budget.directTerms, false),
    processTerms(budget.relatedTerms, true)
  ]);

  // Apply Smart Code Weighting to Radial Results
  if (codeWeight < 1.0) {
    for (const res of allResults) {
      const tags = (res.tags || []).map(t => t.toLowerCase().replace('#', ''));
      const isTechnicalOrCode = tags.some(t => ['code', 'technical', 'json', 'config', 'test'].includes(t));
      const hasChatIndicators = res.content.match(/(^|\n)(User|Human|Assistant|AI|System):/i);
      const isNarrative = tags.some(t => ['narrative', 'relationship', 'social', 'personal'].includes(t)) || !!hasChatIndicators;

      // Also check content heuristics if tags are missing
      const looksLikeCode = res.content.includes('function ') || res.content.includes('const ') || res.content.includes('```');

      // Penalize ONLY if (Tagged Technical OR Looks Like Code) AND NOT Narrative
      if ((isTechnicalOrCode || looksLikeCode) && !isNarrative) {
        res.score = (res.score || 0) * codeWeight;
      }
    }
  }

  // 3. Sort by score and deduplicate by compound+offset, aggregating frequency
  const resultMap = new Map<string, SearchResult & { hits: number }>();

  for (const res of allResults) {
    const key = `${res.compound_id}_${res.start_byte}`;

    if (resultMap.has(key)) {
      const existing = resultMap.get(key)!;
      // Aggregation logic:
      // 1. Increment hits
      existing.hits++;
      // 2. Boost score slightly for each recurrence (Temporal Density)
      existing.score = (existing.score || 0) + ((res.score || 0) * 0.2);
      // 3. Keep the earliest timestamp if we want to show "first seen", or latest? 
      // Let's keep the one with the higher base score (which we already sorted for), 
      // but maybe strict timestamp filtering matters? For now, score aggregation is key.
    } else {
      resultMap.set(key, { ...res, hits: 1 });
    }
  }

  const uniqueResults = Array.from(resultMap.values());
  uniqueResults.sort((a, b) => (b.score || 0) - (a.score || 0));

  // 4. Build context within budget
  let totalChars = 0;
  let context = '';
  const finalResults: SearchResult[] = [];

  for (const res of uniqueResults) {
    const remaining = maxChars - totalChars;
    if (remaining <= 0) break;

    let content = res.content || '';
    if (content.length > remaining) {
      content = content.substring(0, remaining) + '...';
    }

    context += `[${res.source}] (Hits: ${res.hits || 1})\n${content}\n\n`;
    totalChars += content.length;
    finalResults.push({ ...res, content });
  }

  console.log(`[DistributedRadialSearch] Returned ${finalResults.length} results, ${totalChars} chars`);

  return {
    context,
    results: finalResults,
    toAgentString: () => finalResults.map(r => `[${r.source}] (Hits: ${(r as any).hits || 1}) ${r.content}`).join('\n\n'),
    metadata: {
      query,
      directTerms: budget.directTerms.length,
      relatedTerms: budget.relatedTerms.length,
      totalChars,
      resultCount: finalResults.length
    }
  };
}