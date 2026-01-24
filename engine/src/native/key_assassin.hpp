#pragma once
#include <string>
#include <string_view>

namespace ECE {
    class KeyAssassin {
    public:
        // Static method: Takes string, returns clean string
        static std::string Cleanse(std::string_view dirty_content);
    };
}
