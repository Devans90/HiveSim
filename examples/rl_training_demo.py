"""
Example: Training an RL agent to play Hive.

This example demonstrates how to use the HiveEnv with a simple
random policy. For actual training, you would use a library like
Stable-Baselines3, RLlib, or CleanRL.

Note: This is a demonstration of the API. For effective training,
you would need:
1. A proper RL algorithm (PPO, DQN, etc.)
2. Proper hyperparameter tuning
3. Sufficient training time and compute
4. Action masking for efficient learning
"""

from hivesim.env import HiveEnv
from hivesim.robots import RandomBot
import numpy as np


def random_policy_demo():
    """
    Demonstrate using HiveEnv with a random policy.
    This shows the basic training loop structure.
    """
    print("=" * 60)
    print("HiveEnv Random Policy Demo")
    print("=" * 60)
    
    # Create opponent
    opponent = RandomBot(team='black', name='OpponentBot')
    
    # Create environment
    env = HiveEnv(
        agent_team='white',
        opponent=opponent,
        max_turns=100,
        render_mode='ansi',  # or None for no rendering
        reward_shaping=True,  # Enable intermediate rewards
    )
    
    # Training loop structure
    num_episodes = 5
    
    for episode in range(num_episodes):
        obs, info = env.reset(seed=42 + episode)
        
        total_reward = 0
        steps = 0
        terminated = False
        truncated = False
        
        print(f"\nEpisode {episode + 1}")
        print("-" * 40)
        
        while not terminated and not truncated:
            # Get legal actions (use action mask in real training)
            legal_actions = env.get_legal_actions()
            
            if not legal_actions:
                print("No legal actions available!")
                break
            
            # Random policy: choose random legal action
            # In real training, your policy network would output action probabilities
            action = np.random.choice(legal_actions)
            
            # Take action
            obs, reward, terminated, truncated, info = env.step(action)
            
            total_reward += reward
            steps += 1
            
            # Optionally render
            if steps <= 3:  # Show first few steps
                print(f"  Step {steps}: reward={reward:.3f}")
        
        # Episode summary
        if terminated:
            outcome = "WIN" if total_reward > 0 else "LOSS"
        elif truncated:
            outcome = "DRAW (max turns)"
        else:
            outcome = "FORFEIT"
            
        print(f"  Result: {outcome}")
        print(f"  Total reward: {total_reward:.3f}")
        print(f"  Steps: {steps}")
    
    env.close()


def action_mask_demo():
    """
    Demonstrate using action masks for efficient learning.
    
    Action masks are critical for RL in Hive because:
    1. Most actions are illegal at any given time
    2. Taking illegal actions wastes training time
    3. Masked policies learn faster
    """
    print("\n" + "=" * 60)
    print("Action Mask Demo")
    print("=" * 60)
    
    opponent = RandomBot(team='black', name='OpponentBot')
    env = HiveEnv(agent_team='white', opponent=opponent)
    
    obs, info = env.reset(seed=42)
    
    # Get action mask from observation
    action_mask = obs['action_mask']
    
    print(f"Total action space size: {env.action_space.n}")
    print(f"Legal actions: {np.sum(action_mask)}")
    print(f"Illegal actions: {np.sum(action_mask == 0)}")
    
    # In real training with Stable-Baselines3 or similar:
    # - Use MaskablePPO or custom masked policy
    # - Pass action_mask to the policy network
    # - The network will only sample from legal actions
    
    # Example: masked random policy
    legal_action_indices = np.where(action_mask == 1)[0]
    action = np.random.choice(legal_action_indices)
    
    turn = env.action_to_turn(action)
    print(f"\nSelected action: {action}")
    print(f"Turn type: {turn.action_type}")
    if turn.piece_type:
        print(f"Piece type: {turn.piece_type}")
    if turn.target_coordinates:
        print(f"Target: ({turn.target_coordinates.q}, {turn.target_coordinates.r}, {turn.target_coordinates.s})")
    
    env.close()


def observation_structure_demo():
    """
    Demonstrate the observation space structure.
    Understanding the observation is key for designing networks.
    """
    print("\n" + "=" * 60)
    print("Observation Structure Demo")
    print("=" * 60)
    
    env = HiveEnv()
    obs, info = env.reset(seed=42)
    
    # Board observation
    board = obs['board']
    print(f"\nBoard observation shape: {board.shape}")
    print("  - Dim 0-1: Grid positions (21x21 for grid_size=10)")
    print("  - Dim 2: Channels (5)")
    print("    - Channel 0: Piece presence (0/1)")
    print("    - Channel 1: Piece type (0-7)")
    print("    - Channel 2: Team (0=empty, 1=white, 2=black)")
    print("    - Channel 3: Z-level (stacking height)")
    print("    - Channel 4: Can move (1 if piece can legally move)")
    
    # Turn info
    turn_info = obs['turn_info']
    print(f"\nTurn info: {turn_info}")
    print("  - [0]: Normalized turn number")
    print("  - [1]: Current team (1=white, 0=black)")
    print("  - [2]: White queen placed (0/1)")
    print("  - [3]: Black queen placed (0/1)")
    
    # Action mask
    action_mask = obs['action_mask']
    print(f"\nAction mask shape: {action_mask.shape}")
    print(f"Legal actions: {np.sum(action_mask)}")
    
    env.close()


def self_play_structure_demo():
    """
    Demonstrate structure for self-play training.
    Self-play is effective for learning game strategy.
    """
    print("\n" + "=" * 60)
    print("Self-Play Structure Demo")
    print("=" * 60)
    
    # For self-play, you would typically:
    # 1. Train two separate networks (or use the same network for both)
    # 2. Alternate turns between them
    # 3. Update both networks from game experience
    
    # Simple structure using HiveEnv without opponent
    env = HiveEnv(agent_team='white', opponent=None)
    
    obs, info = env.reset(seed=42)
    print("Initial state (no opponent)")
    print(f"  Turn: {info['turn']}")
    print(f"  Current team: {info['current_team']}")
    print(f"  Legal actions: {info['num_legal_actions']}")
    
    # Take agent action
    legal_actions = env.get_legal_actions()
    action = np.random.choice(legal_actions)
    obs, reward, terminated, truncated, info = env.step(action)
    
    print(f"\nAfter agent move:")
    print(f"  Turn: {info['turn']}")
    print(f"  Current team: {info['current_team']}")
    
    # Now it's opponent's turn (in self-play, you'd use another policy)
    # Without opponent, the environment waits for next step() call
    # In self-play training, you would:
    # 1. Use the same env but different policy for opponent
    # 2. Or use two separate environments
    
    print("\nFor full self-play implementation, consider:")
    print("  - Using PettingZoo for multi-agent training")
    print("  - Using RLlib's multi-agent training")
    print("  - Implementing curriculum learning")
    
    env.close()


if __name__ == '__main__':
    random_policy_demo()
    action_mask_demo()
    observation_structure_demo()
    self_play_structure_demo()
    
    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)
    print("\nNext steps for actual training:")
    print("1. Install Stable-Baselines3: pip install stable-baselines3")
    print("2. Use MaskablePPO with action masks")
    print("3. Train for many episodes (millions of steps)")
    print("4. Save and evaluate the trained model")
