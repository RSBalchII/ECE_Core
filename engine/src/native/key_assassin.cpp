#include "key_assassin.hpp"
#include <vector>

namespace ECE {

    std::string KeyAssassin::Cleanse(std::string_view input) {
        std::string result;
        result.reserve(input.size()); // Pre-allocate to prevent reallocation

        // State Machine Flags
        bool escape = false;
        
        // We will do a robust single-pass character filter
        // Logic: 
        // 1. Unescape JSON sequences (\n -> newline, \t -> tab, \" -> ")
        // 2. Strip standard JSON wrappers if detected (naive check for now, can be expanded)
        
        // For now, we replicate the "Unescape" logic which is the most expensive regex in Refiner
        // input.replace(/\\n/g, '\n').replace(/\\"/g, '"')

        for (size_t i = 0; i < input.size(); ++i) {
            char c = input[i];

            if (escape) {
                // Handle escape sequences
                switch (c) {
                    case 'n': result += '\n'; break;
                    case 'r': break; // Drop \r
                    case 't': result += '\t'; break;
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    default: 
                        // Unknown escape, keep literal
                        result += '\\'; 
                        result += c; 
                }
                escape = false;
                continue;
            }

            if (c == '\\') {
                escape = true;
                continue;
            }

            result += c;
        }

        return result;
    }
}
