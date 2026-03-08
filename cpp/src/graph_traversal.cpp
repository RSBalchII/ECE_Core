#include "graph_traversal.h"
#include <queue>
#include <unordered_set>

namespace anchor {

std::vector<Edge> bfsTraversal(Database& db, AtomId start_id, int max_hops) {
    std::vector<Edge> result;
    if (max_hops <= 0) return result;

    std::queue<std::pair<AtomId, int>> q;
    q.push({start_id, 0});

    std::unordered_set<AtomId> visited;
    visited.insert(start_id);

    while (!q.empty()) {
        auto [current_id, depth] = q.front();
        q.pop();

        if (depth >= max_hops) continue;

        std::vector<Edge> edges = db.getEdgesFrom(current_id);
        for (const auto& edge : edges) {
            if (visited.find(edge.to) == visited.end()) {
                visited.insert(edge.to);
                q.push({edge.to, depth + 1});
                result.push_back(edge);
            }
        }
    }

    return result;
}

std::vector<AtomId> findTagNeighbors(Database& db, AtomId atom_id) {
    std::unordered_set<AtomId> neighbor_ids;

    // Get all tags for the source atom
    std::vector<Tag> source_tags = db.getTagsForAtom(atom_id);

    // For each tag, find all atoms sharing that tag
    for (const auto& tag : source_tags) {
        std::vector<Atom> atoms_with_tag = db.getAtomsByTag(tag.tag);
        for (const auto& atom : atoms_with_tag) {
            // Add to neighbors if it's not the original atom
            if (atom.id != atom_id) {
                neighbor_ids.insert(atom.id);
            }
        }
    }

    // Convert set back to vector
    return std::vector<AtomId>(neighbor_ids.begin(), neighbor_ids.end());
}

} // namespace anchor
