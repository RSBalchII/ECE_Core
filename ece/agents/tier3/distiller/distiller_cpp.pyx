# distiller_cpp.pyx
# Cython wrapper for the C++ Distiller implementation

from libcpp.string cimport string
from libcpp.vector cimport vector
from libcpp.map cimport map
from libcpp.pair cimport pair
from libcpp.tuple cimport tuple

# Declare the C++ class
cdef extern from "distiller_core.h":
    cdef cppclass DistillerCore:
        DistillerCore()
        map[string, vector[string]] extract_entities(const string& text)
        vector[tuple[string, string, string]] extract_relationships(
            const string& text, 
            const map[string, vector[string]]& entities)
        string summarize_text(const string& text, int max_length)

# Create a Python wrapper class
cdef class PyDistillerCore:
    cdef DistillerCore* c_distiller  # Hold a C++ instance

    def __cinit__(self):
        self.c_distiller = new DistillerCore()

    def __dealloc__(self):
        del self.c_distiller

    def extract_entities(self, str text):
        cdef string c_text = text.encode('utf-8')
        cdef map[string, vector[string]] c_entities = self.c_distiller.extract_entities(c_text)
        
        entities = {}
        for entity_type, entity_list in c_entities.items():
            entities[entity_type.decode('utf-8')] = [item.decode('utf-8') for item in entity_list]
        
        return entities

    def extract_relationships(self, str text, dict entities):
        # Convert Python dict to C++ map
        cdef map[string, vector[string]] c_entities
        for entity_type, entity_list in entities.items():
            cdef vector[string] c_entity_list
            for entity in entity_list:
                c_entity_list.push_back(entity.encode('utf-8'))
            c_entities[entity_type.encode('utf-8')] = c_entity_list
        
        cdef string c_text = text.encode('utf-8')
        cdef vector[tuple[string, string, string]] c_relationships = \
            self.c_distiller.extract_relationships(c_text, c_entities)
        
        relationships = []
        for rel in c_relationships:
            relationships.append((
                rel[0].decode('utf-8'),
                rel[1].decode('utf-8'),
                rel[2].decode('utf-8')
            ))
        
        return relationships

    def summarize_text(self, str text, int max_length=100):
        cdef string c_text = text.encode('utf-8')
        cdef string c_summary = self.c_distiller.summarize_text(c_text, max_length)
        return c_summary.decode('utf-8')