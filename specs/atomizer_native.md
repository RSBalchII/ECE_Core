# Operation Iron Lung: Phase 2 - The Native Atomizer

**Objective:** Replace `src/services/ingest/atomizer.ts` with a C++ zero-copy streaming splitter.
**Target Metric:** Process 100MB+ logs with < 50MB RAM overhead.

## The Problem
Current JS implementation uses `String.split()` or Regex, which creates millions of substrings. V8's Garbage Collector chokes on massive string arrays, causing latency spikes during ingestion.

## The Solution: `ECE::Atomizer`
A C++ class that scans a `std::string_view` and returns a list of `{ start, length }` tuples (or lightweight objects) representing atoms, rather than copying the text.

### 1. Interface (`src/native/atomizer.hpp`)

```cpp
#pragma once
#include <string_view>
#include <vector>

namespace ECE {
    struct AtomView {
        size_t start;
        size_t length;
        // std::string_view content; // helper
    };

    class Atomizer {
    public:
        // Main Entry point
        static std::vector<AtomView> Atomize(std::string_view content, const std::string& strategy);

    private:
        // Strategy: "code" (Line-based + Bracket balancing)
        static std::vector<AtomView> SplitCode(std::string_view content);
        
        // Strategy: "prose" (Sentence/Paragraph based)
        static std::vector<AtomView> SplitProse(std::string_view content);
    };
}
```

### 2. Strategy Logic

#### A. Code Strategy (The "Block Walker")
Instead of splitting blindly by lines, we track `{}` indentation.
- **Rule**: An atom roughly corresponds to a top-level function or class.
- **Logic**: 
    1. Scan lines.
    2. Track brace depth `depth++` on `{`, `depth--` on `}`.
    3. If `depth == 0` AND `current_length > MIN_SIZE`, emit Atom.
    4. Hard limit at `MAX_SIZE` (4KB) to prevent massive monolithic files from blocking context.

#### B. Prose Strategy (The "Sentence Walker")
- **Logic**:
    1. Scan for `.` `!` `?` `\n\n`.
    2. Accumulate until `TARGET_SIZE` (e.g., 512 chars).
    3. Look for nearest boundary.
    4. Emit Atom.

### 3. N-API Bridge (`src/native/main.cpp`)

We will expose `atomize_indices(text, strategy)`.
Returning the full substrings to JS might still incur copy costs (converting C++ string to JS String).
**Optimization**: 
- JS passes the huge string *once*.
- C++ returns an array of `[start, end]` integers.
- JS `substring()` is very fast (slicing).
- *Alternatively*: If we want to avoid JS-side slicing entirely, we stick to `refiner.ts` processing atoms one by one, but that's complex.
- **Decision**: Return full strings for now, as N-API string creation is inevitable if we want to store them in DB. The win is avoiding the *intermediate* split arrays in C++.

## Implementation Steps
1. Update `binding.gyp` (already compatible).
2. Create `atomizer.hpp` and `atomizer.cpp`.
3. Update `main.cpp` to export `atomize`.
4. Update `refiner.ts` to use `native.atomize()`.
