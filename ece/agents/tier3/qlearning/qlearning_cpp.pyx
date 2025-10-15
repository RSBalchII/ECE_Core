# qlearning_cpp.pyx
# Cython wrapper for the C++ QLearning implementation

from libcpp.vector cimport vector
from libcpp.pair cimport pair

# Declare the C++ class
cdef extern from "qlearning_core.h":
    cdef cppclass QLearningCore:
        QLearningCore(int state_size, int action_size, double learning_rate, double discount_factor, double epsilon)
        int get_action(int state)
        void update_q_value(int state, int action, double reward, int next_state)
        void batch_update_q_values(const vector[int]& states,
                                  const vector[int]& actions,
                                  const vector[double]& rewards,
                                  const vector[int]& next_states)
        vector[int] find_optimal_path(int start_state, int end_state, int max_steps)

# Create a Python wrapper class
cdef class PyQLearningCore:
    cdef QLearningCore* c_qlearning  # Hold a C++ instance

    def __cinit__(self, int state_size, int action_size, 
                   double learning_rate=0.1, double discount_factor=0.95, double epsilon=0.1):
        self.c_qlearning = new QLearningCore(state_size, action_size, learning_rate, discount_factor, epsilon)

    def __dealloc__(self):
        del self.c_qlearning

    def get_action(self, int state):
        return self.c_qlearning.get_action(state)

    def update_q_value(self, int state, int action, double reward, int next_state):
        self.c_qlearning.update_q_value(state, action, reward, next_state)

    def batch_update_q_values(self, list states, list actions, list rewards, list next_states):
        cdef vector[int] c_states = states
        cdef vector[int] c_actions = actions
        cdef vector[double] c_rewards = rewards
        cdef vector[int] c_next_states = next_states
        self.c_qlearning.batch_update_q_values(c_states, c_actions, c_rewards, c_next_states)

    def find_optimal_path(self, int start_state, int end_state, int max_steps=100):
        cdef vector[int] path = self.c_qlearning.find_optimal_path(start_state, end_state, max_steps)
        return [path[i] for i in range(path.size())]