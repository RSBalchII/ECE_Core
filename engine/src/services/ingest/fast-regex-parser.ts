/**
 * Fast Regex-Based Content Parser (Lightweight Alternative to AST/WASM)
 * 
 * Provides rapid content extraction for non-code files (.md, .txt, .jsonl, etc.)
 * without the WASM overhead of tree-sitter AST parsing.
 */

/** Simple block interface for regex parser output */
export interface RegexBlock {
    type: string;
    name: string | null;
    classContext?: string | null;
    startLine: number;
    endLine: number;
    startByte: number;
    endByte: number;
    text?: string;
}

/** Result from regex-based parsing */
export interface RegexParseResult {
    blocks: RegexBlock[];
    imports: string[];
}

/** File extensions that should use AST/WASM parsing (code files) */
const AST_EXTENSIONS = new Set(['ts', 'tsx', 'js', 'jsx']);

/** File extensions that benefit from regex-based structure detection */
const REGEX_STRUCTURE_EXTENSIONS = new Set([
    'md', 'markdown',     // Markdown headings/code blocks
    'jsonl',              // JSON Lines (log/chat data)
    'yml', 'yaml',        // YAML config files  
    'toml',               // TOML config files
]);

/**
 * Check if file extension should use AST parsing vs regex.
 * Code files (.ts, .js, etc.) get full WASM AST parsing.
 * Everything else uses fast regex fallback.
 */
export function shouldUseAstParser(ext: string): boolean {
    return AST_EXTENSIONS.has(ext);
}

/**
 * Extract code block boundaries from content using regex.
 * Returns byte offsets and metadata without WASM parsing.
 */
function extractCodeBlocks(content: string): RegexBlock[] {
    const blocks: RegexBlock[] = [];
    
    // Simple code block detection with regex (fast path)
    const lines = content.split('\n');
    let inCodeBlock = false;
    let blockStartLine = 0;
    let blockType: string | null = 'block';
    let blockName: string | null = null;

    for (const [i, line] of lines.entries()) {
        // Code block start/end detection
        if (/^```/.test(line) && !inCodeBlock) {
            inCodeBlock = true;
            blockStartLine = i + 1; // 1-indexed
            continue;
        }
        
        if (inCodeBlock && /^```\s*$/.test(line)) {
            blocks.push({
                type: blockType || 'block',
                name: blockName,
                startLine: blockStartLine,
                endLine: i + 1,
                startByte: content.indexOf(lines[blockStartLine - 1]),
                endByte: content.indexOf(line),
            });
            inCodeBlock = false;
        }

        // Function/class detection via regex (lightweight)
        const funcMatch = line.match(/^(async\s+)?function\s+(\w+)/);
        if (funcMatch && !inCodeBlock) {
            blocks.push({
                type: 'function',
                name: funcMatch[2],
                startLine: i + 1,
                endLine: i + 1,
                startByte: content.indexOf(line),
                endByte: content.indexOf(line) + line.length,
            });
        }

        const classMatch = line.match(/^(export\s+)?(class|interface)\s+(\w+)/);
        if (classMatch && !inCodeBlock) {
            blocks.push({
                type: 'class',
                name: classMatch[3],
                startLine: i + 1,
                endLine: i + 1,
                startByte: content.indexOf(line),
                endByte: content.indexOf(line) + line.length,
            });
        }
    }

    return blocks;
}

/**
 * Parse markdown structure (headings, sections) using regex.
 */
function parseMarkdownStructure(content: string): RegexParseResult {
    const blocks = extractCodeBlocks(content);
    
    // Add heading-based structural atoms
    const lines = content.split('\n');
    for (const [i, line] of lines.entries()) {
        let headingMatch: RegExpExecArray | null;

        if ((headingMatch = /^#{1}\s+(.+)$/.exec(line))) {
            blocks.push({
                type: 'heading',
                name: `h1-${headingMatch[1].trim().toLowerCase()}`,
                startLine: i + 1,
                endLine: i + 1,
                startByte: content.indexOf(line),
                endByte: content.indexOf(line) + line.length,
            });
        } else if ((headingMatch = /^##\s+(.+)$/.exec(line))) {
            blocks.push({
                type: 'heading',
                name: `h2-${headingMatch[1].trim().toLowerCase()}`,
                startLine: i + 1,
                endLine: i + 1,
                startByte: content.indexOf(line),
                endByte: content.indexOf(line) + line.length,
            });
        } else if ((headingMatch = /^###\s+(.+)$/.exec(line))) {
            blocks.push({
                type: 'heading',
                name: `h3-${headingMatch[1].trim().toLowerCase()}`,
                startLine: i + 1,
                endLine: i + 1,
                startByte: content.indexOf(line),
                endByte: content.indexOf(line) + line.length,
            });
        }
    }

    return { blocks, imports: [] };
}

/**
 * Parse JSONL files with regex (fast path for log/chat data).
 */
function parseJsonlStructure(content: string): RegexParseResult {
    const lines = content.split('\n').filter(line => line.trim());
    const blocks: RegexBlock[] = [];

    // Process in batches of 1000 to avoid memory issues
    const batchSize = Math.min(1000, lines.length);
    
    for (let batchStart = 0; batchStart < lines.length; batchStart += batchSize) {
        const batchEnd = Math.min(batchStart + batchSize, lines.length);
        
        for (const [i, line] of lines.slice(batchStart, batchEnd).entries()) {
            if (!/^\{.*\}\s*$/.test(line)) continue;

            // Extract timestamp if present
            const tsMatch = line.match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
            let name = `entry-${batchStart + i}`;
            
            if (tsMatch) {
                name += `-ts-${tsMatch[0].replace(/[-T:]/g, '')}`;
            }

            blocks.push({
                type: 'entry',
                name,
                startLine: lines.indexOf(line) + 1,
                endLine: lines.indexOf(line) + 1,
                startByte: content.indexOf(line),
                endByte: content.indexOf(line) + line.length,
            });
        }
    }

    return { blocks, imports: [] };
}

/**
 * Parse YAML/TOML config files with regex.
 */
function parseConfigStructure(content: string): RegexParseResult {
    const blocks = extractCodeBlocks(content);
    
    // Extract section headers via regex
    const lines = content.split('\n');
    for (const [i, line] of lines.entries()) {
        const kvMatch = /^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.+)$/.exec(line);
        if (kvMatch && line.length < 100) {
            // Only treat as structural if it looks like a section header
            if (!line.includes(': ') || line.length > 50) {
                blocks.push({
                    type: 'section',
                    name: `section-${kvMatch[1].toLowerCase()}`,
                    startLine: i + 1,
                    endLine: i + 1,
                    startByte: content.indexOf(line),
                    endByte: content.indexOf(line) + line.length,
                });
            }
        }
    }

    return { blocks, imports: [] };
}

/**
 * Detect file type and apply appropriate regex parser.
 * Returns null if no structure detected (will fall back to text splitting).
 */
export function parseWithRegex(
    content: string,
    ext: string,
): RegexParseResult | null {
    const trimmed = content.trim();

    switch (ext) {
        case 'md':
        case 'markdown':
            return parseMarkdownStructure(content);

        case 'jsonl':
            // Verify it's actually JSONL format
            const firstLine = trimmed.split('\n')[0];
            if (/^\{.*\}$/.test(firstLine)) {
                return parseJsonlStructure(content);
            }
            break;

        case 'yml':
        case 'yaml':
        case 'toml':
            return parseConfigStructure(content);
    }

    // For other text files, try generic structure detection
    const hasCodeBlocks = content.includes('```');
    const hasHeadings = /^#{1,6}\s/.test(trimmed.substring(0, 100));
    
    if (hasCodeBlocks || hasHeadings) {
        return parseMarkdownStructure(content);
    }

    // No structure detected - return null for fallback to text splitting
    return null;
}
