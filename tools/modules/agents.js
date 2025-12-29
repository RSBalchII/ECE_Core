import { AnchorLogger } from './anchor.js';

/**
 * THE AUDITOR (Quality Assurance)
 * Enforces the "Clean Table" schema defined by NotebookLM.
 * Rejects memories that don't fit the "Law" of the Graph.
 */
export class MemoryAuditor {
    constructor() {
        this.logger = new AnchorLogger('Auditor');
        
        // The "Law" - Derived from your NotebookLM Table & Specs
        this.schema = {
            required: ['id', 'timestamp', 'role', 'content'],
            roles: ['user', 'assistant', 'system', 'file', 'manual', 'thought'],
            constraints: {
                id_format: /^[0-9]+-[a-z0-9]+$/, // e.g. "1735165200000-x9s8d7f"
                content_min_len: 1,
                content_max_len: 20000 // Limit for WASM stability
            }
        };
    }

    /**
     * Audit a proposed memory before insertion.
     * @param {Object} memory - The candidate memory object
     * @returns {Object} { passed: boolean, reason: string }
     */
    audit(memory) {
        // 1. Schema Check (Missing Fields)
        for (const field of this.schema.required) {
            if (memory[field] === undefined || memory[field] === null) {
                return this._reject(`Missing required field: ${field}`);
            }
        }

        // 2. Type Safety
        if (typeof memory.id !== 'string') return this._reject("ID must be a string");
        if (typeof memory.timestamp !== 'number') return this._reject("Timestamp must be a number");
        if (typeof memory.content !== 'string') return this._reject("Content must be a string");

        // 3. Role Enforcement
        if (!this.schema.roles.includes(memory.role)) {
            return this._reject(`Invalid Role: '${memory.role}'. Allowed: ${this.schema.roles.join(', ')}`);
        }

        // 4. Content Hygiene
        if (memory.content.length < this.schema.constraints.content_min_len) {
            return this._reject("Content is empty");
        }
        
        // Auto-Truncate warning (Auditor doesn't modify, just warns/rejects)
        if (memory.content.length > this.schema.constraints.content_max_len) {
            this.logger.warn(`Content exceeds safety limit (${memory.content.length} chars). Truncation recommended.`);
            // We allow it but warn, assuming Builder/Console handles truncation
        }

        // 5. Logic Check (Timestamp Sanity)
        // If timestamp is from 1970 (0) or future (> 1 day ahead), flag it
        const now = Date.now();
        const oneDay = 86400000;
        if (memory.timestamp < 1000000000000) return this._reject("Timestamp appears to be in seconds, not ms (or invalid)");
        if (memory.timestamp > now + oneDay) return this._reject("Timestamp is in the future");

        return { passed: true, reason: "Valid" };
    }

    _reject(reason) {
        this.logger.warn(`Audit Failed: ${reason}`);
        return { passed: false, reason };
    }
}