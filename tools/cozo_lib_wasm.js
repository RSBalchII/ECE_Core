import { loadAllFromIndexedDb, flushPendingWrites, writeToIndexedDb, setWriteCounter } from './indexeddb.js';

let wasm;

const heap = new Array(128).fill(undefined);

heap.push(undefined, null, true, false);

function getObject(idx) { return heap[idx]; }

let heap_next = heap.length;

function dropObject(idx) {
    if (idx < 132) return;
    heap[idx] = heap_next;
    heap_next = idx;
}

function takeObject(idx) {
    const ret = getObject(idx);
    dropObject(idx);
    return ret;
}

const cachedTextDecoder = (typeof TextDecoder !== 'undefined' ? new TextDecoder('utf-8', { ignoreBOM: true, fatal: true }) : { decode: () => { throw Error('TextDecoder not available') } } );

if (typeof TextDecoder !== 'undefined') { cachedTextDecoder.decode(); };

let cachedUint8Memory0 = null;

function getUint8Memory0() {
    if (cachedUint8Memory0 === null || cachedUint8Memory0.byteLength === 0) {
        cachedUint8Memory0 = new Uint8Array(wasm.memory.buffer);
    }
    return cachedUint8Memory0;
}

function getStringFromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return cachedTextDecoder.decode(getUint8Memory0().subarray(ptr, ptr + len));
}

function addHeapObject(obj) {
    if (heap_next === heap.length) heap.push(heap.length + 1);
    const idx = heap_next;
    heap_next = heap[idx];

    heap[idx] = obj;
    return idx;
}

function makeMutClosure(arg0, arg1, dtor, f) {
    const state = { a: arg0, b: arg1, cnt: 1, dtor };
    const real = (...args) => {
        // First up with a closure we increment the internal reference
        // count. This ensures that the Rust closure environment won't
        // be deallocated while we're invoking it.
        state.cnt++;
        const a = state.a;
        state.a = 0;
        try {
            return f(a, state.b, ...args);
        } finally {
            if (--state.cnt === 0) {
                wasm.__wbindgen_export_0.get(state.dtor)(a, state.b);

            } else {
                state.a = a;
            }
        }
    };
    real.original = state;

    return real;
}
function __wbg_adapter_22(arg0, arg1, arg2) {
    wasm.wasm_bindgen__convert__closures__invoke1_mut__hd17e34166836fd48(arg0, arg1, addHeapObject(arg2));
}

let WASM_VECTOR_LEN = 0;

const cachedTextEncoder = (typeof TextEncoder !== 'undefined' ? new TextEncoder('utf-8') : { encode: () => { throw Error('TextEncoder not available') } } );

const encodeString = (typeof cachedTextEncoder.encodeInto === 'function'
    ? function (arg, view) {
    return cachedTextEncoder.encodeInto(arg, view);
}
    : function (arg, view) {
    const buf = cachedTextEncoder.encode(arg);
    view.set(buf);
    return {
        read: arg.length,
        written: buf.length
    };
});

function passStringToWasm0(arg, malloc, realloc) {
    if (typeof arg !== 'string') arg = arg ? String(arg) : "";
    if (realloc === undefined) {
        const buf = cachedTextEncoder.encode(arg);
        const ptr = malloc(buf.length, 1) >>> 0;
        getUint8Memory0().subarray(ptr, ptr + buf.length).set(buf);
        WASM_VECTOR_LEN = buf.length;
        return ptr;
    }

    let len = arg.length;
    let ptr = malloc(len, 1) >>> 0;

    const mem = getUint8Memory0();

    let offset = 0;

    for (; offset < len; offset++) {
        const code = arg.charCodeAt(offset);
        if (code > 0x7F) break;
        mem[ptr + offset] = code;
    }

    if (offset !== len) {
        if (offset !== 0) {
            arg = arg.slice(offset);
        }
        ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
        const view = getUint8Memory0().subarray(ptr + offset, ptr + len);
        const ret = encodeString(arg, view);

        offset += ret.written;
    }

    WASM_VECTOR_LEN = offset;
    return ptr;
}

let cachedInt32Memory0 = null;

function getInt32Memory0() {
    if (cachedInt32Memory0 === null || cachedInt32Memory0.byteLength === 0) {
        cachedInt32Memory0 = new Int32Array(wasm.memory.buffer);
    }
    return cachedInt32Memory0;
}

function handleError(f, args) {
    try {
        return f.apply(this, args);
    } catch (e) {
        wasm.__wbindgen_exn_store(addHeapObject(e));
    }
}
function __wbg_adapter_76(arg0, arg1, arg2, arg3) {
    wasm.wasm_bindgen__convert__closures__invoke2_mut__h62fdc46dd4e23c5d(arg0, arg1, addHeapObject(arg2), addHeapObject(arg3));
}

/**
*/
export class CozoDb {

    static __wrap(ptr) {
        ptr = ptr >>> 0;
        const obj = Object.create(CozoDb.prototype);
        obj.__wbg_ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_cozodb_free(ptr);
    }
    /**
    * @returns {CozoDb}
    */
    static new() {
        const ret = wasm.cozodb_new();
        return CozoDb.__wrap(ret);
    }
    /**
    * Create CozoDb from IndexedDB
    * @param {string} db_name
    * @param {string} store_name
    * @param {any} on_write_callback
    * @returns {Promise<CozoDb>}
    */
    static new_from_indexed_db(db_name, store_name, on_write_callback) {
        const ptr0 = passStringToWasm0(db_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(store_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.cozodb_new_from_indexed_db(ptr0, len0, ptr1, len1, addHeapObject(on_write_callback));
        return takeObject(ret);
    }
    /**
    * @param {string} script
    * @param {string} params
    * @param {boolean} immutable
    * @returns {Promise<string>}
    */
    run(script, params, immutable) {
        if (typeof params === 'undefined' || params === null) params = "{}";
        const ptr0 = passStringToWasm0(script, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(params, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.cozodb_run(this.__wbg_ptr, ptr0, len0, ptr1, len1, immutable);
        return takeObject(ret);
    }
    /**
    * @param {string} data
    * @returns {string}
    */
    export_relations(data) {
        let deferred2_0;
        let deferred2_1;
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            const ptr0 = passStringToWasm0(data, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            wasm.cozodb_export_relations(retptr, this.__wbg_ptr, ptr0, len0);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            deferred2_0 = r0;
            deferred2_1 = r1;
            return getStringFromWasm0(r0, r1);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
    * @param {string} data
    * @returns {string}
    */
    import_relations(data) {
        // Normalize common JSON payload shapes so the WASM importer receives
        // a canonical `{"relations": [{ name, headers, rows }]}` shape.
        let normalized = null;
        try {
            const parsed = JSON.parse(data);
            // Top-level 'memory' -> convert
            if (parsed && parsed.memory) {
                const mem = parsed.memory;
                const headers = mem.headers || (mem.named_rows && mem.named_rows.headers) || null;
                const rows = mem.rows || (mem.named_rows && mem.named_rows.rows) || [];
                normalized = { relations: [{ name: 'memory', headers: headers || [], rows }] };
            }
            // Already a relations wrapper
            else if (parsed && parsed.relations && Array.isArray(parsed.relations)) {
                const rels = parsed.relations.map(r => {
                    const headers = r.headers || (r.named_rows && r.named_rows.headers) || (r.NamedRows && r.NamedRows.headers) || ['id','timestamp','role','content','source','embedding'];
                    const rawRows = r.rows || (r.named_rows && r.named_rows.rows) || (r.NamedRows && r.NamedRows.rows) || [];
                    const rows = rawRows.map(row => {
                        // Normalize object rows into arrays using headers order
                        if (row && typeof row === 'object' && !Array.isArray(row)) {
                            return headers.map(h => (row[h] === undefined ? null : row[h]));
                        }
                        // Ensure array rows have proper length and default embedding
                        const arr = Array.isArray(row) ? row.slice(0, headers.length) : [];
                        while (arr.length < headers.length) arr.push(null);
                        const embIdx = headers.indexOf('embedding');
                        if (embIdx >= 0 && (arr[embIdx] === null || arr[embIdx] === undefined)) arr[embIdx] = [];
                        return arr;
                    });
                    // Provide multiple shapes to satisfy various importer variants
                    return {
                        name: r.name || 'memory',
                        headers,
                        rows,
                        named_rows: { headers, rows },
                        NamedRows: { headers, rows }
                    };
                });
                normalized = { relations: rels };
            }
            // Else, could be raw array of records -> convert to rows
            else if (Array.isArray(parsed)) {
                const rows = parsed.map(rec => {
                    const ts = rec.timestamp ? (isNaN(Number(rec.timestamp)) ? new Date(rec.timestamp).getTime() : Number(rec.timestamp)) : Date.now();
                    return [
                        `${ts}-${Math.random().toString(36).substr(2,9)}`,
                        ts,
                        rec.role || rec.type || 'unknown',
                        (rec.content || rec.response_content || rec.message || '').substring(0, 20000),
                        rec.source || 'combined_memory.json',
                        null
                    ];
                });
                normalized = { relations: [{ name: 'memory', headers: ['id','timestamp','role','content','source','embedding'], rows }] };
            }
        } catch (e) {
            // Not valid JSON or normalization failed; fall back to raw string
        }

        const payload = normalized ? JSON.stringify(normalized) : data;

        let deferred2_0;
        let deferred2_1;
        try {
            // Debug: show the exact payload being passed into WASM importer (trimmed)
            try {
                console.log('CozoDb.import_relations - payload preview (trimmed):', payload.slice(0, 2000));
                const parsedPreview = JSON.parse(payload);
                console.log('CozoDb.import_relations - parsed relations preview:', parsedPreview.relations && parsedPreview.relations[0] ? Object.keys(parsedPreview.relations[0]) : null);
            } catch (pe) {
                console.warn('CozoDb.import_relations - payload not parseable as JSON preview.');
            }
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            const ptr0 = passStringToWasm0(payload, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            try {
                wasm.cozodb_import_relations(retptr, this.__wbg_ptr, ptr0, len0);
            } catch (e) {
                console.error('CozoDb.import_relations wasm call failed:', e, 'payload_preview:', payload.slice(0,2000));
                throw e;
            }
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            deferred2_0 = r0;
            deferred2_1 = r1;
            const resultStr = getStringFromWasm0(r0, r1);

            // If WASM returned a NamedRows header error, try a fallback shaped payload where relation includes NamedRows explicitly.
            try {
                const parsedResult = JSON.parse(resultStr);
                if (parsedResult && parsedResult.ok === false && typeof parsedResult.message === 'string' && parsedResult.message.includes('NamedRows requires')) {
                    try {
                        const parsedPayload = JSON.parse(payload);
                        if (parsedPayload && parsedPayload.relations && Array.isArray(parsedPayload.relations)) {
                            const fallback = { relations: parsedPayload.relations.map(r => ({ name: r.name || 'memory', NamedRows: { headers: r.headers || (r.named_rows && r.named_rows.headers) || (r.NamedRows && r.NamedRows.headers) || ['id','timestamp','role','content','source','embedding'], rows: r.rows || (r.named_rows && r.named_rows.rows) || (r.NamedRows && r.NamedRows.rows) || [] } })) };
                            const fallbackStr = JSON.stringify(fallback);
                            console.log('CozoDb.import_relations - retrying with fallback NamedRows payload (trimmed):', fallbackStr.slice(0,2000));
                            const ptrF = passStringToWasm0(fallbackStr, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                            const lenF = WASM_VECTOR_LEN;
                            wasm.cozodb_import_relations(retptr, this.__wbg_ptr, ptrF, lenF);
                            var r0b = getInt32Memory0()[retptr / 4 + 0];
                            var r1b = getInt32Memory0()[retptr / 4 + 1];
                            // free previous
                            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
                            deferred2_0 = r0b;
                            deferred2_1 = r1b;
                            return getStringFromWasm0(r0b, r1b);
                        }
                    } catch (retryErr) {
                        console.warn('CozoDb.import_relations - fallback retry failed to build payload or call wasm:', retryErr);
                    }
                }
            } catch (e) {
                // ignore parse errors
            }

            return resultStr;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
}

async function __wbg_load(module, imports) {
    if (typeof Response === 'function' && module instanceof Response) {
        if (typeof WebAssembly.instantiateStreaming === 'function') {
            try {
                return await WebAssembly.instantiateStreaming(module, imports);

            } catch (e) {
                if (module.headers.get('Content-Type') != 'application/wasm') {
                    console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                } else {
                    throw e;
                }
            }
        }

        const bytes = await module.arrayBuffer();
        return await WebAssembly.instantiate(bytes, imports);

    } else {
        const instance = await WebAssembly.instantiate(module, imports);

        if (instance instanceof WebAssembly.Instance) {
            return { instance, module };

        } else {
            return instance;
        }
    }
}

function __wbg_get_imports() {
    const imports = {};
    imports.wbg = {};
    imports.wbg.__wbindgen_object_drop_ref = function(arg0) {
        takeObject(arg0);
    };
    imports.wbg.__wbg_log_b78d654f19d681e0 = function(arg0, arg1) {
        console.log(getStringFromWasm0(arg0, arg1));
    };
    imports.wbg.__wbg_loadAllFromIndexedDb_05f8df9a19c8d344 = function(arg0, arg1, arg2, arg3, arg4) {
        const ret = loadAllFromIndexedDb(getStringFromWasm0(arg0, arg1), getStringFromWasm0(arg2, arg3), getObject(arg4));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_flushPendingWrites_dd4341a0dafcf428 = function() {
        const ret = flushPendingWrites();
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_string_new = function(arg0, arg1) {
        const ret = getStringFromWasm0(arg0, arg1);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_cozodb_new = function(arg0) {
        const ret = CozoDb.__wrap(arg0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_cb_drop = function(arg0) {
        const obj = takeObject(arg0).original;
        if (obj.cnt-- == 1) {
            obj.a = 0;
            return true;
        }
        const ret = false;
        return ret;
    };
    imports.wbg.__wbg_new_abda76e883ba8a5f = function() {
        const ret = new Error();
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_stack_658279fe44541cf6 = function(arg0, arg1) {
        const ret = getObject(arg1).stack;
        const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        getInt32Memory0()[arg0 / 4 + 1] = len1;
        getInt32Memory0()[arg0 / 4 + 0] = ptr1;
    };
    imports.wbg.__wbg_error_f851667af71bcfc6 = function(arg0, arg1) {
        let deferred0_0;
        let deferred0_1;
        try {
            deferred0_0 = arg0;
            deferred0_1 = arg1;
            console.error(getStringFromWasm0(arg0, arg1));
        } finally {
            wasm.__wbindgen_free(deferred0_0, deferred0_1, 1);
        }
    };
    imports.wbg.__wbg_setWriteCounter_295838a9805b3542 = function(arg0) {
        setWriteCounter(arg0 >>> 0);
    };
    imports.wbg.__wbg_writeToIndexedDb_ec8ba47108ce4d3a = function(arg0, arg1) {
        const ret = writeToIndexedDb(getObject(arg0), getObject(arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_crypto_c48a774b022d20ac = function(arg0) {
        const ret = getObject(arg0).crypto;
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_is_object = function(arg0) {
        const val = getObject(arg0);
        const ret = typeof(val) === 'object' && val !== null;
        return ret;
    };
    imports.wbg.__wbg_process_298734cf255a885d = function(arg0) {
        const ret = getObject(arg0).process;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_versions_e2e78e134e3e5d01 = function(arg0) {
        const ret = getObject(arg0).versions;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_node_1cd7a5d853dbea79 = function(arg0) {
        const ret = getObject(arg0).node;
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_is_string = function(arg0) {
        const ret = typeof(getObject(arg0)) === 'string';
        return ret;
    };
    imports.wbg.__wbg_msCrypto_bcb970640f50a1e8 = function(arg0) {
        const ret = getObject(arg0).msCrypto;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_require_8f08ceecec0f4fee = function() { return handleError(function () {
        const ret = module.require;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbindgen_is_function = function(arg0) {
        const ret = typeof(getObject(arg0)) === 'function';
        return ret;
    };
    imports.wbg.__wbg_randomFillSync_dc1e9a60c158336d = function() { return handleError(function (arg0, arg1) {
        getObject(arg0).randomFillSync(takeObject(arg1));
    }, arguments) };
    imports.wbg.__wbg_getRandomValues_37fa2ca9e4e07fab = function() { return handleError(function (arg0, arg1) {
        getObject(arg0).getRandomValues(getObject(arg1));
    }, arguments) };
    imports.wbg.__wbg_get_44be0491f933a435 = function(arg0, arg1) {
        const ret = getObject(arg0)[arg1 >>> 0];
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_length_fff51ee6522a1a18 = function(arg0) {
        const ret = getObject(arg0).length;
        return ret;
    };
    imports.wbg.__wbg_newnoargs_581967eacc0e2604 = function(arg0, arg1) {
        const ret = new Function(getStringFromWasm0(arg0, arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_call_cb65541d95d71282 = function() { return handleError(function (arg0, arg1) {
        const ret = getObject(arg0).call(getObject(arg1));
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbindgen_object_clone_ref = function(arg0) {
        const ret = getObject(arg0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_self_1ff1d729e9aae938 = function() { return handleError(function () {
        const ret = self.self;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_window_5f4faef6c12b79ec = function() { return handleError(function () {
        const ret = window.window;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_globalThis_1d39714405582d3c = function() { return handleError(function () {
        const ret = globalThis.globalThis;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_global_651f05c6a0944d1c = function() { return handleError(function () {
        const ret = global.global;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbindgen_is_undefined = function(arg0) {
        const ret = getObject(arg0) === undefined;
        return ret;
    };
    imports.wbg.__wbg_isArray_4c24b343cb13cfb1 = function(arg0) {
        const ret = Array.isArray(getObject(arg0));
        return ret;
    };
    imports.wbg.__wbg_call_01734de55d61e11d = function() { return handleError(function (arg0, arg1, arg2) {
        const ret = getObject(arg0).call(getObject(arg1), getObject(arg2));
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_now_9c5990bda04c7e53 = function() {
        const ret = Date.now();
        return ret;
    };
    imports.wbg.__wbg_new_43f1b47c28813cbd = function(arg0, arg1) {
        try {
            var state0 = {a: arg0, b: arg1};
            var cb0 = (arg0, arg1) => {
                const a = state0.a;
                state0.a = 0;
                try {
                    return __wbg_adapter_76(a, state0.b, arg0, arg1);
                } finally {
                    state0.a = a;
                }
            };
            const ret = new Promise(cb0);
            return addHeapObject(ret);
        } finally {
            state0.a = state0.b = 0;
        }
    };
    imports.wbg.__wbg_resolve_53698b95aaf7fcf8 = function(arg0) {
        const ret = Promise.resolve(getObject(arg0));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_then_f7e06ee3c11698eb = function(arg0, arg1) {
        const ret = getObject(arg0).then(getObject(arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_then_b2267541e2a73865 = function(arg0, arg1, arg2) {
        const ret = getObject(arg0).then(getObject(arg1), getObject(arg2));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_buffer_085ec1f694018c4f = function(arg0) {
        const ret = getObject(arg0).buffer;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_newwithbyteoffsetandlength_6da8e527659b86aa = function(arg0, arg1, arg2) {
        const ret = new Uint8Array(getObject(arg0), arg1 >>> 0, arg2 >>> 0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_new_8125e318e6245eed = function(arg0) {
        const ret = new Uint8Array(getObject(arg0));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_set_5cf90238115182c3 = function(arg0, arg1, arg2) {
        getObject(arg0).set(getObject(arg1), arg2 >>> 0);
    };
    imports.wbg.__wbg_length_72e2208bbc0efc61 = function(arg0) {
        const ret = getObject(arg0).length;
        return ret;
    };
    imports.wbg.__wbg_instanceof_Uint8Array_d8d9cb2b8e8ac1d4 = function(arg0) {
        let result;
        try {
            result = getObject(arg0) instanceof Uint8Array;
        } catch {
            result = false;
        }
        const ret = result;
        return ret;
    };
    imports.wbg.__wbg_newwithlength_e5d69174d6984cd7 = function(arg0) {
        const ret = new Uint8Array(arg0 >>> 0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_subarray_13db269f57aa838d = function(arg0, arg1, arg2) {
        const ret = getObject(arg0).subarray(arg1 >>> 0, arg2 >>> 0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_throw = function(arg0, arg1) {
        throw new Error(getStringFromWasm0(arg0, arg1));
    };
    imports.wbg.__wbindgen_memory = function() {
        const ret = wasm.memory;
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_closure_wrapper186 = function(arg0, arg1, arg2) {
        const ret = makeMutClosure(arg0, arg1, 87, __wbg_adapter_22);
        return addHeapObject(ret);
    };

    return imports;
}

function __wbg_init_memory(imports, maybe_memory) {

}

function __wbg_finalize_init(instance, module) {
    wasm = instance.exports;
    __wbg_init.__wbindgen_wasm_module = module;
    cachedInt32Memory0 = null;
    cachedUint8Memory0 = null;


    return wasm;
}

function initSync(module) {
    if (wasm !== undefined) return wasm;

    const imports = __wbg_get_imports();

    __wbg_init_memory(imports);

    if (!(module instanceof WebAssembly.Module)) {
        module = new WebAssembly.Module(module);
    }

    const instance = new WebAssembly.Instance(module, imports);

    return __wbg_finalize_init(instance, module);
}

async function __wbg_init(input) {
    if (wasm !== undefined) return wasm;

    if (typeof input === 'undefined') {
        input = new URL('cozo_lib_wasm_bg.wasm', import.meta.url);
    }
    const imports = __wbg_get_imports();

    if (typeof input === 'string' || (typeof Request === 'function' && input instanceof Request) || (typeof URL === 'function' && input instanceof URL)) {
        input = fetch(input);
    }

    __wbg_init_memory(imports);

    const { instance, module } = await __wbg_load(await input, imports);

    return __wbg_finalize_init(instance, module);
}

export { initSync }
export default __wbg_init;
