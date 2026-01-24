/**
 * Dreamer Service - Markovian Memory Organization with Epochal Historian
 *
 * Implements:
 * 1. Markovian reasoning for background memory organization
 * 2. Deterministic Temporal Tagging for grounding memories in time
 * 3. Epochal Historian for identifying Epochs, Episodes, and Entities
 */

import { db } from '../../core/db.js';
import wink from 'wink-nlp';
import model from 'wink-eng-lite-web-model';

// Initialize Wink-NLP (Low-Memory Model)
const nlp = wink(model);

// AsyncLock implementation for preventing concurrent dream cycles
class AsyncLock {
  private locked = false;
  private waiting: Array<(releaser: () => void) => void> = [];

  async acquire(): Promise<() => void> {
    if (!this.locked) {
      this.locked = true;
      return this.release.bind(this);
    }

    return new Promise<() => void>((resolve) => {
      this.waiting.push(resolve);
    });
  }

  private release(): void {
    if (this.waiting.length > 0) {
      const next = this.waiting.shift();
      if (next) next(this.release.bind(this));
    } else {
      this.locked = false;
    }
  }

  get isLocked(): boolean {
    return this.locked;
  }
}

const dreamLock = new AsyncLock();

// Temporal constants
const SEASONS: { [key: number]: string } = {
  0: 'Winter', 1: 'Winter', 2: 'Spring',
  3: 'Spring', 4: 'Spring', 5: 'Summer',
  6: 'Summer', 7: 'Summer', 8: 'Autumn',
  9: 'Autumn', 10: 'Autumn', 11: 'Winter'
};

const QUARTERS: { [key: number]: string } = {
  0: 'Q1', 1: 'Q1', 2: 'Q1',
  3: 'Q2', 4: 'Q2', 5: 'Q2',
  6: 'Q3', 7: 'Q3', 8: 'Q3',
  9: 'Q4', 10: 'Q4', 11: 'Q4'
};

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/**
 * Generates deterministic temporal tags based on the timestamp
 */
function generateTemporalTags(timestamp: number): string[] {
  if (!timestamp) return [];

  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return [];

  const tags = new Set<string>();
  const monthIndex = date.getMonth();

  // Core Date Units
  tags.add(date.getFullYear().toString());
  tags.add(MONTHS[monthIndex]);
  tags.add(DAYS[date.getDay()]);

  // Broad Temporal Buckets
  tags.add(SEASONS[monthIndex]);
  tags.add(QUARTERS[monthIndex]);

  // Time of Day
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) tags.add('Morning');
  else if (hour >= 12 && hour < 17) tags.add('Afternoon');
  else if (hour >= 17 && hour < 21) tags.add('Evening');
  else tags.add('Night');

  return Array.from(tags);
}

/**
 * Performs background memory organization using Markovian reasoning
 * Identifies Epochs, Episodes, and Entities as part of the Epochal Historian
 */
export async function dream(): Promise<{ status: string; analyzed?: number; updated?: number; message?: string }> {
  // Check if a dream cycle is already running
  if (dreamLock.isLocked) {
    return {
      status: 'skipped',
      message: 'Previous dream cycle still running'
    };
  }

  const release = await dreamLock.acquire();

  try {
    console.log('🌙 Dreamer: Starting self-organization cycle...');

    // 1. Get all memories that might benefit from re-categorization
    const allMemoriesQuery = '?[id, content, buckets, timestamp] := *memory{id, content, buckets, timestamp}';
    const allMemoriesResult = await db.run(allMemoriesQuery);

    if (!allMemoriesResult.rows || allMemoriesResult.rows.length === 0) {
      return { status: 'success', analyzed: 0, message: 'No memories to analyze' };
    }

    // Filter memories that need attention
    const memoriesToAnalyze = allMemoriesResult.rows.filter((row: any[]) => {
      const [_, __, buckets, timestamp] = row;

      // Always include memories with no buckets
      if (!buckets || buckets.length === 0) return true;

      // Include memories with generic buckets
      const genericBuckets = ['core', 'misc', 'general', 'other', 'unknown'];
      const hasOnlyGenericBuckets = buckets.every((bucket: string) => genericBuckets.includes(bucket));
      if (hasOnlyGenericBuckets) return true;

      // Include memories that lack temporal tags
      const year = new Date(timestamp).getFullYear().toString();
      if (!buckets.includes(year)) return true;

      return false;
    });

    console.log(`🌙 Dreamer: Found ${memoriesToAnalyze.length} memories to analyze.`);

    let updatedCount = 0;

    // Process in batches using Shared Module
    const { processInBatches } = await import('../../core/batch.js');
    const { config } = await import('../../config/index.js');
    const batchSize = config.DREAMER_BATCH_SIZE || 5;

    const totalBatches = Math.ceil(memoriesToAnalyze.length / batchSize);
    await processInBatches(memoriesToAnalyze, async (batch: any[], batchIndex: number) => {
      const batchStartTime = Date.now();
      if ((batchIndex + 1) % 5 === 0 || batchIndex === 0 || batchIndex === totalBatches - 1) {
        console.log(`[Dreamer] Processing batch ${batchIndex + 1}/${totalBatches} (${batch.length} memories)...`);
      }

      // 1. Prepare updates mapping in memory
      const updatesMap = new Map<string, string[]>();
      for (const row of batch) {
        const [id, _content, currentBuckets, timestamp] = row;
        const temporalTags = generateTemporalTags(timestamp);

        let newSemanticTags: string[] = [];
        const meaningfulBuckets = (currentBuckets || []).filter((b: string) =>
          !['core', 'pending'].includes(b) && !/^\d{4}$/.test(b)
        );

        if (meaningfulBuckets.length < 2) {
          newSemanticTags = ['semantic_tag_placeholder'];
        }

        const combinedBuckets = [...new Set([...(currentBuckets || []), ...newSemanticTags, ...temporalTags])];
        let finalBuckets = [...combinedBuckets];
        if (combinedBuckets.length > 1) {
          const specificBuckets = combinedBuckets.filter((b: string) =>
            !['core', 'pending', 'misc', 'general', 'other', 'unknown', 'inbox'].includes(b)
          );
          if (specificBuckets.length > 0) {
            finalBuckets = specificBuckets;
          }
        }
        updatesMap.set(id, finalBuckets);
      }

      // 2. Bulk fetch full data for the batch
      const flatIds = batch.map(r => r[0]);
      const fetchQuery = `
        ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] :=
        id in $flatIds,
        *memory{id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}
      `;
      const fullDataResult = await db.run(fetchQuery, { flatIds });

      if (fullDataResult.rows && fullDataResult.rows.length > 0) {
        const finalUpdateData = fullDataResult.rows.map((row: any) => {
          const id = row[0];
          const newBuckets = updatesMap.get(id);
          const updatedRow = [...row];
          updatedRow[8] = newBuckets; // index 8 is buckets
          return updatedRow;
        });

        // 3. Bulk Update
        await db.run(`
          ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding] <- $data
          :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, simhash, embedding}
        `, { data: finalUpdateData });

        updatedCount += finalUpdateData.length;
      }

      const batchDuration = Date.now() - batchStartTime;
      const rate = Math.round((batch.length / (batchDuration / 1000)) * 10) / 10;
      if (batchDuration > 500) {
        console.log(`[Dreamer] Batch ${batchIndex + 1}/${totalBatches} completed in ${batchDuration}ms (${rate} items/sec)`);
      }
    }, { batchSize });

    // PHASE 21: Tag Infection Protocol (Standard 068)
    try {
      console.log('🌙 Dreamer: Running Tag Infection cycle...');
      const { runDiscovery } = await import('../tags/discovery.js');
      const { runInfectionLoop } = await import('../tags/infector.js');

      // 1. Teacher learns from a sample
      await runDiscovery(30);
      // 2. Student infects the entire graph
      await runInfectionLoop();
    } catch (infectionError: any) {
      console.error('🌙 Dreamer: Tag Infection failed:', infectionError.message);
    }

    // NEW: The Abstraction Pyramid - Cluster and Summarize into Episodes/Epochs
    await clusterAndSummarize();

    // MIRROR PROTOCOL: Export to Notebook
    try {
      console.log('🌙 Dreamer: Triggering Mirror Protocol...');
      // Dynamic import to handle JS file and potential circular deps
      const { createMirror } = await import('../mirror/mirror.js');
      await createMirror();
    } catch (mirrorError: any) {
      console.error('🌙 Dreamer: Mirror Protocol failed:', mirrorError.message);
    }

    return {
      status: 'success',
      analyzed: memoriesToAnalyze.length,
      updated: updatedCount
    };
  } catch (error) {
    console.error('🌙 Dreamer Fatal Error:', error);
    throw error;
  } finally {
    release();
  }
}

/**
 * The Abstraction Pyramid: Clusters Atoms into Episodes and Epochs
 * Uses Iterative Summarization to prevent Context Window overflow.
 */
async function clusterAndSummarize(): Promise<void> {
  try {
    console.log('🌙 Dreamer: Running Abstraction Pyramid analysis...');

    // 1. Find Unbound Atoms (Level 1 Nodes without a Parent)
    const { config } = await import('../../config/index.js');
    const limit = (config.DREAMER_BATCH_SIZE || 5) * 4; // Fetch 4x batch size for clustering context

    // We look for memories that are NOT a child in 'parent_of'
    // Cozo: `?[id] := *memory{id}, not *parent_of{child_id: id}`
    // We look for memories that are NOT a child in 'parent_of'
    // Cozo: `?[id] := *memory{id}, not *parent_of{child_id: id}`
    const unboundQuery = `
            ?[id, timestamp, content, tags] := *memory{id, timestamp, content, tags},
            not *parent_of{child_id: id},
            :order timestamp
    :limit ${limit}
    `;
    const result = await db.run(unboundQuery);

    if (!result.rows || result.rows.length === 0) {
      console.log('🌙 Dreamer: No unbound atoms found.');
      return;
    }

    const atoms = result.rows.map((r: any[]) => ({
      id: r[0],
      timestamp: r[1],
      content: r[2],
      tags: r[3] || [] // Fetch tags
    }));
    console.log(`🌙 Dreamer: Found ${atoms.length} unbound atoms.Clustering...`);

    // 2. Temporal Clustering (Gap > 15 minutes = New Cluster)
    const clusters: any[][] = [];
    let currentCluster: any[] = [];
    let lastTime = atoms[0].timestamp;

    for (const atom of atoms) {
      if (atom.timestamp - lastTime > config.DREAMER_CLUSTERING_GAP_MS) {
        if (currentCluster.length > 0) clusters.push(currentCluster);
        currentCluster = [];
      }
      currentCluster.push(atom);
      lastTime = atom.timestamp;
    }
    if (currentCluster.length > 0) clusters.push(currentCluster);

    // 3. Process Clusters -> Episodes (Level 2)
    console.log(`🌙 Dreamer: Processing ${clusters.length} temporal clusters...`);
    let clusterIndex = 0;
    for (const cluster of clusters) {
      clusterIndex++;
      if (cluster.length < 3) continue; // Skip tiny clusters for now, wait for more context?
      // Or just summarize them if they are old enough?
      // For now, let's process clusters of size >= 3.

      console.log(`🌙 Dreamer: Summarizing cluster of ${cluster.length} atoms...`);


      // 3. Process Clusters -> Episodes (Level 2)
      console.log(`🌙 Dreamer: Summarizing cluster of ${cluster.length} atoms (Deterministic Episode)...`);

      // DETERMINISTIC EPISODE GENERATION (Standard 072)
      // Instead of LLM, we use pure metadata extraction for the Episode Node.
      // This is O(1) and instant.

      // A. Extract Date Range
      const startTime = cluster[0].timestamp;
      const endTime = cluster[cluster.length - 1].timestamp;

      // B. Concatenate content for Wink Analysis
      const fullText = cluster.map((a: any) => a.content).join('\n');

      // C. Extract Entities & Keywords using Wink
      const doc = nlp.readDoc(fullText);

      // Get top entities (if any)
      // Filter: Must be > 2 chars, exclude numbers
      const entities = doc.entities().out(nlp.its.value, nlp.as.freqTable)
        .filter((e: any) => e[0].length > 2 && !/^\d+$/.test(e[0]))
        .slice(0, 10)
        .map((e: any) => e[0]);

      // D. Aggregate Tags (The "Sovereign" Context)
      // Instead of weak NLP nouns, we harvest the high-quality tags from the atoms themselves.
      const tagCounts = new Map<string, number>();
      cluster.forEach((atom: any) => {
        atom.tags.forEach((tag: string) => {
          tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
        });
      });

      // Sort tags by frequency
      const topics = Array.from(tagCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8)
        .map(entry => entry[0]);

      // Fallback: If no tags, try basic NLP nouns
      if (topics.length === 0) {
        const nouns = doc.tokens()
          .filter((t: any) => t.out(nlp.its.pos) === 'NOUN' && !t.out((nlp.its as any).stopWord))
          .out(nlp.its.normal, nlp.as.freqTable)
          .filter((t: any) => t[0].length > 3 && !/^[0-9]+$/.test(t[0]))
          .slice(0, 5)
          .map((t: any) => t[0]);
        topics.push(...nouns);
      }

      // D. Construct Metadata-Rich Content
      const episodeContent = `
EPISODE HEADER
Range: ${new Date(startTime).toISOString()} - ${new Date(endTime).toISOString()}
Topics: ${topics.join(', ')}
Entities: ${entities.join(', ')}
Atom Count: ${cluster.length}
      `.trim();

      // Create Episode Node (Level 2)
      const crypto = await import('crypto');
      const summaryHash = crypto.createHash('sha256').update(episodeContent).digest('hex');
      const episodeId = `ep_${summaryHash.substring(0, 16)}`;

      // Insert Summary Node
      await db.run(
        `?[id, type, content, span_start, span_end, embedding] <- [[$id, $type, $content, $start, $end, $emb]]
      :put summary_node { id, type, content, span_start, span_end, embedding }`,
        {
          id: episodeId,
          type: 'episode',
          content: episodeContent,
          start: startTime,
          end: endTime,
          emb: new Array(384).fill(0.0) // Placeholder
        }
      );

      // Link Atoms to Episode (Parent_Of)
      const edges = cluster.map(atom => [episodeId, atom.id, 1.0]);
      await db.run(
        `?[parent_id, child_id, weight] <- $edges :put parent_of { parent_id, child_id, weight }`,
        { edges }
      );

      console.log(`🌙 Dreamer: Created Episode ${episodeId} (Topics: ${topics.join(', ')})`);
    }

  } catch (e: any) {
    console.error('🌙 Dreamer: Error in Abstraction Pyramid:', e.message);
  }
}