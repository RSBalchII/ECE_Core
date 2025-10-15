#include "distiller_core.h"
#include <sstream>
#include <algorithm>
#include <cctype>

DistillerCore::DistillerCore() {
    initialize_patterns();
}

DistillerCore::~DistillerCore() {
    // Cleanup if needed
}

void DistillerCore::initialize_patterns() {
    // Compile regex patterns for different entity types
    entity_patterns_["person"] = std::regex(R"(\b[A-Z][a-z]+ [A-Z][a-z]+\b)");
    entity_patterns_["organization"] = std::regex(R"(\b[A-Z][A-Z]+\b|\b[A-Z][a-z]+ [A-Z][a-z]+\b)");
    entity_patterns_["location"] = std::regex(R"(\b[A-Z][a-z]+(?: [A-Z][a-z]+)*, [A-Z]{2}\b|\b[A-Z][a-z]+(?: [A-Z][a-z]*)* (?:St|Ave|Rd|Blvd|Dr|Ln|Ct|Pl)\b)");
    entity_patterns_["date"] = std::regex(R"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2},? \d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b)");
    entity_patterns_["email"] = std::regex(R"(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b)");
    entity_patterns_["url"] = std::regex(R"(https?://[^\s<>"]+|www\.[^\s<>"]+)");
}

std::map<std::string, std::vector<std::string>> DistillerCore::extract_entities(const std::string& text) {
    std::map<std::string, std::vector<std::string>> entities;
    
    for (const auto& [entity_type, pattern] : entity_patterns_) {
        std::vector<std::string> matches;
        std::sregex_iterator iter(text.begin(), text.end(), pattern);
        std::sregex_iterator end;
        
        while (iter != end) {
            std::string match = iter->str();
            
            // Check if this match is already in our list to avoid duplicates
            if (std::find(matches.begin(), matches.end(), match) == matches.end()) {
                matches.push_back(match);
            }
            ++iter;
        }
        
        entities[entity_type] = matches;
    }
    
    return entities;
}

std::vector<std::tuple<std::string, std::string, std::string>> DistillerCore::extract_relationships(
    const std::string& text, 
    const std::map<std::string, std::vector<std::string>>& entities) {
    
    std::vector<std::tuple<std::string, std::string, std::string>> relationships;
    
    // Split text into sentences (simplified approach)
    std::vector<std::string> sentences;
    std::istringstream iss(text);
    std::string sentence;
    while (std::getline(iss, sentence, '.')) {
        sentences.push_back(sentence);
    }
    
    // Look for relationships between entities in each sentence
    for (const auto& sentence : sentences) {
        for (const auto& [entity_type1, entity_list1] : entities) {
            for (const auto& entity1 : entity_list1) {
                if (sentence.find(entity1) != std::string::npos) {
                    for (const auto& [entity_type2, entity_list2] : entities) {
                        for (const auto& entity2 : entity_list2) {
                            if (entity2 != entity1 && sentence.find(entity2) != std::string::npos) {
                                // Add a relationship between entities
                                std::string rel_type = "RELATED_TO_" + entity_type2;
                                relationships.push_back(std::make_tuple(entity1, rel_type, entity2));
                            }
                        }
                    }
                }
            }
        }
    }
    
    // Remove duplicate relationships
    std::sort(relationships.begin(), relationships.end());
    relationships.erase(
        std::unique(relationships.begin(), relationships.end()),
        relationships.end()
    );
    
    return relationships;
}

std::string DistillerCore::summarize_text(const std::string& text, int max_length) {
    std::istringstream iss(text);
    std::string token;
    std::vector<std::string> tokens;
    
    // Split text into tokens (words)
    while (iss >> token) {
        tokens.push_back(token);
    }
    
    if (static_cast<int>(tokens.size()) <= max_length) {
        return text;
    }
    
    // Simple truncation summary (first max_length tokens)
    std::string summary;
    for (int i = 0; i < max_length && i < static_cast<int>(tokens.size()); ++i) {
        if (i > 0) summary += " ";
        summary += tokens[i];
    }
    
    return summary;
}