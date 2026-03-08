#include "graph_traversal.h"
#include "database.h"
#include <iostream>
#include <cassert>
#include <vector>
#include <optional>

using namespace anchor;

void test_bfs() {
    std::cout << "Testing BFS Traversal..." << std::endl;

    // Create in-memory database
    Database db = Database::inMemory();

    // Insert sources first
    Source s1;
    s1.id = "src1";
    s1.path = "path/to/src1";
    s1.created_at = 100.0;
    s1.updated_at = 100.0;
    db.upsertSource(s1);

    Source s2;
    s2.id = "src2";
    s2.path = "path/to/src2";
    s2.created_at = 100.0;
    s2.updated_at = 100.0;
    db.upsertSource(s2);

    Atom a1;
    a1.source_id = "src1";
    a1.content = "content1";
    a1.char_start = 0;
    a1.char_end = 10;
    a1.timestamp = 100.0;
    a1.simhash = 0x123;
    AtomId id1 = db.insertAtom(a1);

    Atom a2;
    a2.source_id = "src1";
    a2.content = "content2";
    a2.char_start = 10;
    a2.char_end = 20;
    a2.timestamp = 101.0;
    a2.simhash = 0x124;
    AtomId id2 = db.insertAtom(a2);

    Atom a3;
    a3.source_id = "src2";
    a3.content = "content3";
    a3.char_start = 0;
    a3.char_end = 10;
    a3.timestamp = 102.0;
    a3.simhash = 0x125;
    AtomId id3 = db.insertAtom(a3);

    Atom a4;
    a4.source_id = "src2";
    a4.content = "content4";
    a4.char_start = 10;
    a4.char_end = 20;
    a4.timestamp = 103.0;
    a4.simhash = 0x126;
    AtomId id4 = db.insertAtom(a4);

    // Insert edges: 1->2, 1->3, 2->4
    Edge e1;
    e1.from = id1;
    e1.to = id2;
    e1.weight = 1.0;
    e1.edge_type = "test";
    db.insertEdge(e1);

    Edge e2;
    e2.from = id1;
    e2.to = id3;
    e2.weight = 1.0;
    e2.edge_type = "test";
    db.insertEdge(e2);

    Edge e3;
    e3.from = id2;
    e3.to = id4;
    e3.weight = 1.0;
    e3.edge_type = "test";
    db.insertEdge(e3);

    // BFS from 1 with max_hops=2
    std::vector<Edge> result_edges = bfsTraversal(db, id1, 2);

    std::cout << "Traversed " << result_edges.size() << " edges." << std::endl;

    // Check results
    bool found_1_2 = false;
    bool found_1_3 = false;
    bool found_2_4 = false;

    for (const auto& e : result_edges) {
        std::cout << "Edge: " << e.from << " -> " << e.to << std::endl;
        if (e.from == id1 && e.to == id2) found_1_2 = true;
        if (e.from == id1 && e.to == id3) found_1_3 = true;
        if (e.from == id2 && e.to == id4) found_2_4 = true;
    }

    assert(result_edges.size() == 3);
    (void)found_1_2; assert(found_1_2);
    (void)found_1_3; assert(found_1_3);
    (void)found_2_4; assert(found_2_4);

    std::cout << "BFS Traversal Test Passed!" << std::endl;
}

void test_findTagNeighbors() {
    std::cout << "Testing findTagNeighbors..." << std::endl;

    // Create in-memory database
    Database db = Database::inMemory();

    // Insert sources first
    Source s1;
    s1.id = "src1";
    s1.path = "path/to/src1";
    s1.created_at = 100.0;
    s1.updated_at = 100.0;
    db.upsertSource(s1);

    // Insert atoms
    Atom a1;
    a1.source_id = "src1";
    a1.content = "content1";
    AtomId id1 = db.insertAtom(a1);

    Atom a2;
    a2.source_id = "src1";
    a2.content = "content2";
    AtomId id2 = db.insertAtom(a2);

    Atom a3;
    a3.source_id = "src1";
    a3.content = "content3";
    AtomId id3 = db.insertAtom(a3);

    Atom a4;
    a4.source_id = "src1";
    a4.content = "content4";
    AtomId id4 = db.insertAtom(a4);

    // Add tags
    // a1 has tags "A", "B"
    db.addTags(id1, {
        {0, id1, "A", std::nullopt},
        {0, id1, "B", std::nullopt}
    });

    // a2 has tags "B", "C"
    db.addTags(id2, {
        {0, id2, "B", std::nullopt},
        {0, id2, "C", std::nullopt}
    });

    // a3 has tag "A"
    db.addTags(id3, {
        {0, id3, "A", std::nullopt}
    });

    // a4 has tag "D" (no overlap)
    db.addTags(id4, {
        {0, id4, "D", std::nullopt}
    });

    // Test a1 neighbors
    // Should return id2 (shares "B") and id3 (shares "A")
    std::vector<AtomId> a1_neighbors = findTagNeighbors(db, id1);
    assert(a1_neighbors.size() == 2);

    bool found_id2 = false;
    bool found_id3 = false;
    for (AtomId neighbor_id : a1_neighbors) {
        if (neighbor_id == id2) found_id2 = true;
        if (neighbor_id == id3) found_id3 = true;
        // Verify we don't return the source atom itself
        assert(neighbor_id != id1);
    }
    (void)found_id2; assert(found_id2);
    (void)found_id3; assert(found_id3);

    // Test a2 neighbors
    // Should return id1 (shares "B")
    std::vector<AtomId> a2_neighbors = findTagNeighbors(db, id2);
    assert(a2_neighbors.size() == 1);
    assert(a2_neighbors[0] == id1);

    // Test a3 neighbors
    // Should return id1 (shares "A")
    std::vector<AtomId> a3_neighbors = findTagNeighbors(db, id3);
    assert(a3_neighbors.size() == 1);
    assert(a3_neighbors[0] == id1);

    // Test a4 neighbors
    // Should return empty (no shared tags)
    std::vector<AtomId> a4_neighbors = findTagNeighbors(db, id4);
    assert(a4_neighbors.empty());

    // Test deduplication
    // Let's add tag "A" to a2 as well, so a1 and a2 now share "A" and "B"
    db.addTags(id2, {
        {0, id2, "A", std::nullopt}
    });

    a1_neighbors = findTagNeighbors(db, id1);
    assert(a1_neighbors.size() == 2); // Still just id2 and id3, deduplicated correctly

    found_id2 = false;
    found_id3 = false;
    for (AtomId neighbor_id : a1_neighbors) {
        if (neighbor_id == id2) found_id2 = true;
        if (neighbor_id == id3) found_id3 = true;
    }
    (void)found_id2; assert(found_id2);
    (void)found_id3; assert(found_id3);

    std::cout << "findTagNeighbors Test Passed!" << std::endl;
}

int main() {
    try {
        test_bfs();
        test_findTagNeighbors();
    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
