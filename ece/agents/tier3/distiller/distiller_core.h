#ifndef DISTILLER_CORE_H
#define DISTILLER_CORE_H

#include <string>
#include <vector>
#include <map>
#include <regex>

class DistillerCore {
public:
    // Constructor
    DistillerCore();

    // Destructor
    ~DistillerCore();

    // Extract named entities from text
    std::map<std::string, std::vector<std::string>> extract_entities(const std::string& text);

    // Extract relationships between entities in text
    std::vector<std::tuple<std::string, std::string, std::string>> extract_relationships(
        const std::string& text, 
        const std::map<std::string, std::vector<std::string>>& entities);

    // Create a summary of the text
    std::string summarize_text(const std::string& text, int max_length = 100);

private:
    // Precompiled regex patterns for different entity types
    std::map<std::string, std::regex> entity_patterns_;
    
    // Compile regex patterns during initialization
    void initialize_patterns();
};

#endif // DISTILLER_CORE_H