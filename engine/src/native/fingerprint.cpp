#include "fingerprint.hpp"
#include <array>

#ifdef _MSC_VER
#include <intrin.h> // For __popcnt64 on MSVC
#endif

namespace ECE {

    // FNV-1a 64-bit Hash for Token Robustness
    uint64_t Fingerprint::HashToken(std::string_view token) {
        uint64_t hash = 14695981039346656037ULL;
        for (char c : token) {
            hash ^= static_cast<uint64_t>(c);
            hash *= 1099511628211ULL;
        }
        return hash;
    }

    uint64_t Fingerprint::Generate(std::string_view input) {
        // SimHash Vector: 64 buckets initialized to 0
        std::array<int, 64> weights = {0};
        
        size_t start = 0;
        size_t len = input.length();

        // Tokenizer Loop: Split by whitespace (Basic)
        // Advanced versions use n-grams, but word-level is sufficient for document dedupe.
        for (size_t i = 0; i <= len; ++i) {
            // Delimiter check: simple whitespace chars
            bool is_delimiter = (i == len) || (input[i] == ' ' || input[i] == '\n' || input[i] == '\t' || input[i] == '\r');
            
            if (is_delimiter) {
                if (i > start) {
                    // Extract token
                    std::string_view token = input.substr(start, i - start);
                    
                    // Hash the token into 64 bits
                    uint64_t h = HashToken(token);

                    // Update Weights: 
                    // If bit K is 1, increment weight[K]. Else decrement.
                    for (int bit = 0; bit < 64; ++bit) {
                        if (h & (1ULL << bit)) {
                            weights[bit]++;
                        } else {
                            weights[bit]--;
                        }
                    }
                }
                start = i + 1;
            }
        }

        // Collapse Weights into Final Hash
        uint64_t fingerprint = 0;
        for (int bit = 0; bit < 64; ++bit) {
            if (weights[bit] > 0) {
                fingerprint |= (1ULL << bit);
            }
        }

        return fingerprint;
    }

    int Fingerprint::Distance(uint64_t a, uint64_t b) {
        uint64_t x = a ^ b; // XOR reveals differing bits
        
        // Hamming Weight (Population Count)
        // Portable implementation selection
        #if defined(__GNUC__) || defined(__clang__)
            return __builtin_popcountll(x);
        #elif defined(_MSC_VER)
            return static_cast<int>(__popcnt64(x));
        #else
            // Software Fallback (Brian Kernighan's Algorithm)
            int count = 0;
            while (x) {
                x &= (x - 1);
                count++;
            }
            return count;
        #endif
    }
}
