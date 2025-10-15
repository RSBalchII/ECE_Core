#include "qlearning_core.h"
#include <algorithm>
#include <numeric>
#include <stdexcept>

QLearningCore::QLearningCore(int state_size, int action_size, double learning_rate, double discount_factor, double epsilon)
    : state_size_(state_size), action_size_(action_size), learning_rate_(learning_rate), 
      discount_factor_(discount_factor), epsilon_(epsilon), gen_(std::random_device{}()), dis_(0.0, 1.0) {
    // Initialize Q-table with zeros
    q_table_.resize(state_size_, std::vector<double>(action_size_, 0.0));
}

QLearningCore::~QLearningCore() {
    // Cleanup if needed
}

int QLearningCore::get_action(int state) {
    if (state < 0 || state >= state_size_) {
        throw std::out_of_range("State index out of range");
    }

    // Use epsilon-greedy policy
    if (dis_(gen_) < epsilon_) {
        // Explore: random action
        return static_cast<int>(dis_(gen_) * action_size_);
    } else {
        // Exploit: best known action
        auto& state_actions = q_table_[state];
        return std::distance(state_actions.begin(), 
                            std::max_element(state_actions.begin(), state_actions.end()));
    }
}

void QLearningCore::update_q_value(int state, int action, double reward, int next_state) {
    if (state < 0 || state >= state_size_) {
        throw std::out_of_range("State index out of range");
    }
    if (action < 0 || action >= action_size_) {
        throw std::out_of_range("Action index out of range");
    }
    if (next_state < 0 || next_state >= state_size_) {
        throw std::out_of_range("Next state index out of range");
    }

    double current_q = q_table_[state][action];
    auto& next_state_actions = q_table_[next_state];
    double max_next_q = *std::max_element(next_state_actions.begin(), next_state_actions.end());
    
    double new_q = current_q + learning_rate_ * (reward + discount_factor_ * max_next_q - current_q);
    q_table_[state][action] = new_q;
}

void QLearningCore::batch_update_q_values(const std::vector<int>& states, 
                                          const std::vector<int>& actions, 
                                          const std::vector<double>& rewards, 
                                          const std::vector<int>& next_states) {
    size_t batch_size = states.size();
    
    if (actions.size() != batch_size || rewards.size() != batch_size || next_states.size() != batch_size) {
        throw std::invalid_argument("All input vectors must have the same size");
    }
    
    for (size_t i = 0; i < batch_size; ++i) {
        update_q_value(states[i], actions[i], rewards[i], next_states[i]);
    }
}

std::vector<int> QLearningCore::find_optimal_path(int start_state, int end_state, int max_steps) {
    if (start_state < 0 || start_state >= state_size_) {
        throw std::out_of_range("Start state index out of range");
    }
    if (end_state < 0 || end_state >= state_size_) {
        throw std::out_of_range("End state index out of range");
    }

    std::vector<int> path;
    path.push_back(start_state);
    int current_state = start_state;
    
    for (int step = 0; step < max_steps; ++step) {
        if (current_state == end_state) {
            break;
        }
        
        int action = get_action(current_state);
        // For this simple implementation, transition is deterministic based on action
        int next_state = (current_state + action) % state_size_;
        path.push_back(next_state);
        current_state = next_state;
    }
    
    return path;
}