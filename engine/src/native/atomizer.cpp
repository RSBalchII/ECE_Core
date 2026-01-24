#include "atomizer.hpp"
#include <algorithm>

namespace ECE {

    std::vector<std::string> Atomizer::Atomize(std::string_view content, const std::string& strategy) {
        if (strategy == "code") {
            return SplitCode(content);
        }
        return SplitProse(content);
    }

    std::vector<std::string> Atomizer::SplitCode(std::string_view content) {
        std::vector<std::string> atoms;
        size_t len = content.size();
        size_t start = 0;
        int depth = 0;
        size_t last_split = 0;
        
        // Tunables
        const size_t MIN_SIZE = 200; // Minimum characters per atom
        const size_t MAX_SIZE = 4000; // Hard limit

        // Very simple robust scanner
        for (size_t i = 0; i < len; ++i) {
            char c = content[i];

            if (c == '{') depth++;
            else if (c == '}') {
                if (depth > 0) depth--;
            }

            // Check for split condition
            size_t current_len = i - last_split;

            // Trigger: Top level (depth 0), at newline, and big enough
            // OR soft max limit reached
            bool is_newline = (c == '\n');
            bool at_zero_depth = (depth == 0);
            
            if (is_newline && at_zero_depth && current_len > MIN_SIZE) {
                atoms.emplace_back(content.substr(last_split, current_len + 1));
                last_split = i + 1;
                continue;
            }

            // Hard limit safety (split at newline if possible, else forced)
            if (current_len >= MAX_SIZE) {
                // Find nearest newline backwards
                size_t back_scan = i;
                bool found_cut = false;
                while (back_scan > last_split && (i - back_scan) < 200) { // Look back 200 chars
                    if (content[back_scan] == '\n') {
                        atoms.emplace_back(content.substr(last_split, (back_scan - last_split) + 1));
                        last_split = back_scan + 1;
                        // Reset i to sync? strictly no need if we just continue
                        found_cut = true;
                        break;
                    }
                    back_scan--;
                }
                if (!found_cut) {
                    // Force split
                    atoms.emplace_back(content.substr(last_split, current_len));
                    last_split = i + 1;
                }
            }
        }

        // Remainder
        if (last_split < len) {
            atoms.emplace_back(content.substr(last_split));
        }

        return atoms;
    }

    std::vector<std::string> Atomizer::SplitProse(std::string_view content) {
        std::vector<std::string> atoms;
        size_t len = content.size();
        size_t last_split = 0;
        
        // Tunables
        const size_t TARGET_SIZE = 600; // Prefer ~600 chars
        const size_t MAX_SIZE = 1500;   // Hard limit

        for (size_t i = 0; i < len; ++i) {
            size_t current_len = i - last_split;

            // Optimization: Skip scan if too small
            if (current_len < TARGET_SIZE) continue;

            char c = content[i];
            
            // Check for sentence/paragraph boundaries
            // We look for ". " or "\n\n"
            bool is_boundary = false;
            if (c == '\n') {
                // Look ahead for another newline
                if (i + 1 < len && content[i+1] == '\n') is_boundary = true;
            } else if (c == '.' || c == '!' || c == '?') {
                if (i + 1 < len && (content[i+1] == ' ' || content[i+1] == '\n')) is_boundary = true;
            }

            if (is_boundary || current_len >= MAX_SIZE) {
                // Include the punctuation/newline
                size_t cut_len = current_len + 1;
                if (c == '\n' && i+1 < len && content[i+1] == '\n') cut_len++; // Eat the second newline

                atoms.emplace_back(content.substr(last_split, cut_len));
                last_split = last_split + cut_len;
                i = last_split - 1; // Advance loop
            }
        }

        // Remainder
        if (last_split < len) {
            atoms.emplace_back(content.substr(last_split));
        }

        return atoms;
    }
}
