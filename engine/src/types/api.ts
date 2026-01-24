
export interface Menu {
    id: string;
    content: string;
    source: string;
    type: string;
    timestamp: number;
    buckets: string[];
    tags: string;
    epochs: string;
    provenance: string;
    score?: number;
}

export interface SearchRequest {
    query: string;           // The natural language query
    limit?: number;          // Elastic Window (default 20)
    max_chars?: number;      // Character budget
    deep?: boolean;          // If true, trigger 'Epochal' search (Dreamer layers)

    // The "UniversalRAG" Routing Layer
    buckets?: string[];      // e.g., ["@code", "@visual", "@memory"]
    provenance?: 'internal' | 'external' | 'quarantine' | 'all'; // Data Provenance filter
}

export interface SearchResponse {
    context: string;
    results: Menu[];
    metadata: {
        engram_hits: number;   // Did we find exact entity matches?
        vector_latency: number;
        provenance_boost_active: boolean;
    }
}
