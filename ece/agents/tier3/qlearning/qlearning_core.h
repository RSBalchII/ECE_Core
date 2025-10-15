#ifndef QLEARNING_CORE_H
#define QLEARNING_CORE_H

#include <vector>
#include <random>

class QLearningCore {
public:
    // Constructor
    QLearningCore(int state_size, int action_size, double learning_rate = 0.1, double discount_factor = 0.95, double epsilon = 0.1);

    // Destructor
    ~QLearningCore();

    // Get action using epsilon-greedy policy
    int get_action(int state);

    // Update Q-value for a state-action pair
    void update_q_value(int state, int action, double reward, int next_state);

    // Batch update Q-values for multiple experiences
    void batch_update_q_values(const std::vector<int>& states, 
                              const std::vector<int>& actions, 
                              const std::vector<double>& rewards, 
                              const std::vector<int>& next_states);

    // Find an optimal path (simplified implementation)
    std::vector<int> find_optimal_path(int start_state, int end_state, int max_steps = 100);

private:
    int state_size_;
    int action_size_;
    double learning_rate_;
    double discount_factor_;
    double epsilon_;
    std::vector<std::vector<double>> q_table_;
    std::mt19937 gen_;
    std::uniform_real_distribution<double> dis_;
};

#endif // QLEARNING_CORE_H