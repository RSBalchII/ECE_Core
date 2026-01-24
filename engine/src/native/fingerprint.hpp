#pragma once
#include <string>
#include <string_view>
#include <vector>
#include <cstdint>

namespace ECE {
    class Fingerprint {
    public:
        // Returns a 64-bit SimHash of the input text
        static uint64_t Generate(std::string_view input);
        
        // Returns the Hamming Distance (0-64) between two hashes
        // Lower number = More similar
        static int Distance(uint64_t a, uint64_t b);

    private:
        // A simple, fast hashing function for individual tokens (FNV-1a)
        static uint64_t HashToken(std::string_view token);
    };
}
