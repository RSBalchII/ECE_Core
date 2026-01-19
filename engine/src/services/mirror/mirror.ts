/**
 * Mirror Protocol Service - "Tangible Knowledge Graph"
 *
 * Projects the AI Brain onto the filesystem using a @bucket/#tag structure.
 */

import * as fs from 'fs';
import * as path from 'path';
import { db } from '../../core/db.js';
import { NOTEBOOK_DIR } from '../../config/paths.js';

export const MIRRORED_BRAIN_PATH = path.join(NOTEBOOK_DIR, 'mirrored_brain');

// Clean filename helper
function sanitizeFilename(text: string): string {
    return text.replace(/[^a-zA-Z0-9-_]/g, '_').substring(0, 64);
}

/**
 * Mirror Protocol: Exports memories to Markdown files organized by @bucket/#tag
 */
export async function createMirror() {
    console.log('🪞 Mirror Protocol: Starting semantic brain mirroring...');

    if (!fs.existsSync(MIRRORED_BRAIN_PATH)) {
        fs.mkdirSync(MIRRORED_BRAIN_PATH, { recursive: true });
    }

    const query = '?[id, timestamp, content, source, type, hash, buckets, tags] := *memory{id, timestamp, content, source, type, hash, buckets, tags}';
    const result = await db.run(query);

    if (!result.rows || result.rows.length === 0) {
        console.log('🪞 Mirror Protocol: No memories to mirror.');
        return;
    }

    console.log(`🪞 Mirror Protocol: Mirroring ${result.rows.length} memories to disk...`);

    let count = 0;
    for (const row of result.rows) {
        const [id, timestamp, content, source, type, _hash, buckets, tags] = row;

        // Buckets and tags come as arrays from Cozo
        const bucketList = (buckets as string[]) || [];
        const tagList = (tags as string[]) || [];
        const primaryBucket = bucketList.length > 0 ? bucketList[0] : 'general';

        await writeMirrorFile({
            id: id as string,
            timestamp: timestamp as number,
            content: content as string,
            source: source as string,
            type: type as string,
            bucket: primaryBucket,
            tags: tagList
        });
        count++;
    }

    console.log(`🪞 Mirror Protocol: Synchronization complete. ${count} memories mirrored to ${MIRRORED_BRAIN_PATH}`);
}

async function writeMirrorFile(memory: any) {
    try {
        // 1. Determine Bucket (Root Folder)
        const bucketName = (memory.bucket && memory.bucket !== 'general' && memory.bucket !== 'unknown') ? memory.bucket : 'general';
        const bucketDir = path.join(MIRRORED_BRAIN_PATH, `@${sanitizeFilename(bucketName)}`);

        // 2. Determine Primary Tag (Sub Folder)
        // Filter out the bucket name and inbox from tags to find the 'Topic'
        const specificTags = memory.tags.filter((t: string) => t !== bucketName && t !== 'inbox');
        const tagName = specificTags.length > 0 ? specificTags[0] : '_untagged';
        const tagDir = path.join(bucketDir, `#${sanitizeFilename(tagName)}`);

        // Create Dirs
        if (!fs.existsSync(tagDir)) {
            fs.mkdirSync(tagDir, { recursive: true });
        }

        // 3. Generate Filename (Semantic Snippet + ID Suffix)
        let nameSnippet = "note";
        // Try to find a title in markdown (# Title)
        const titleMatch = memory.content.match(/^#\s+(.+)$/m);
        if (titleMatch) {
            nameSnippet = titleMatch[1];
        } else {
            // Fallback to first few words
            nameSnippet = memory.content.substring(0, 30).trim().split('\n')[0];
        }

        const safeName = sanitizeFilename(nameSnippet).toLowerCase();
        // Short ID for uniqueness
        const shortId = (memory.id || "").split('_').pop() || "anon";

        let extension = '.md';
        if (memory.type === 'json') extension = '.json';

        const filePath = path.join(tagDir, `${safeName}_${shortId}${extension}`);

        // 4. Write Frontmatter + Content
        const frontmatter = `---
id: ${memory.id}
date: ${new Date(memory.timestamp).toISOString()}
source: ${memory.source}
bucket: ${memory.bucket}
tags: ${JSON.stringify(memory.tags)}
---

`;
        await fs.promises.writeFile(filePath, frontmatter + memory.content, 'utf8');
        return true;
    } catch (e: any) {
        console.error(`Failed to write mirror file for ${memory.id}:`, e.message);
        return false;
    }
}

