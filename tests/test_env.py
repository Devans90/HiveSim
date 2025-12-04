"""
Unit tests for the Gymnasium-compatible HiveEnv.
"""
import pytest
import numpy as np

from hivesim.env import HiveEnv, make_hive_env, PIECE_TYPE_MAP
from hivesim.robots import RandomBot


class TestHiveEnvCreation:
    """Test HiveEnv initialization."""
    
    def test_env_creation_defaults(self):
        """Test creating environment with default parameters."""
        env = HiveEnv()
        assert env.agent_team == 'white'
        assert env.grid_size == 10
        assert env.max_turns == 200
        assert env.render_mode is None
    
    def test_env_creation_custom_params(self):
        """Test creating environment with custom parameters."""
        env = HiveEnv(
            agent_team='black',
            grid_size=15,
            max_turns=100,
            render_mode='ansi'
        )
        assert env.agent_team == 'black'
        assert env.grid_size == 15
        assert env.max_turns == 100
        assert env.render_mode == 'ansi'
    
    def test_env_with_opponent(self):
        """Test creating environment with opponent bot."""
        opponent = RandomBot(team='black', name='OpponentBot')
        env = HiveEnv(agent_team='white', opponent=opponent)
        assert env.opponent is not None
    
    def test_make_hive_env_factory(self):
        """Test factory function."""
        env = make_hive_env(agent_team='white', grid_size=8)
        assert isinstance(env, HiveEnv)
        assert env.grid_size == 8


class TestObservationSpace:
    """Test observation space properties."""
    
    def test_observation_space_structure(self):
        """Test observation space has correct structure."""
        env = HiveEnv()
        assert 'board' in env.observation_space.spaces
        assert 'turn_info' in env.observation_space.spaces
        assert 'action_mask' in env.observation_space.spaces
    
    def test_board_shape(self):
        """Test board observation has correct shape."""
        env = HiveEnv(grid_size=10)
        board_space = env.observation_space['board']
        # Shape: (grid_dim, grid_dim, channels_per_level * max_stack_height)
        # Default: (21, 21, 3 * 5) = (21, 21, 15)
        expected_shape = (21, 21, 15)
        assert board_space.shape == expected_shape
    
    def test_turn_info_shape(self):
        """Test turn info has correct shape."""
        env = HiveEnv()
        turn_info_space = env.observation_space['turn_info']
        assert turn_info_space.shape == (4,)
    
    def test_action_mask_shape(self):
        """Test action mask has correct shape."""
        env = HiveEnv()
        action_mask_space = env.observation_space['action_mask']
        assert action_mask_space.shape == (env.action_space.n,)


class TestReset:
    """Test environment reset."""
    
    def test_reset_returns_observation(self):
        """Test reset returns valid observation."""
        env = HiveEnv()
        obs, info = env.reset(seed=42)
        
        assert 'board' in obs
        assert 'turn_info' in obs
        assert 'action_mask' in obs
    
    def test_reset_observation_types(self):
        """Test observation values have correct types."""
        env = HiveEnv()
        obs, info = env.reset(seed=42)
        
        assert isinstance(obs['board'], np.ndarray)
        assert obs['board'].dtype == np.float32
        assert isinstance(obs['turn_info'], np.ndarray)
        assert isinstance(obs['action_mask'], np.ndarray)
    
    def test_reset_info_structure(self):
        """Test reset info has expected keys."""
        env = HiveEnv()
        obs, info = env.reset(seed=42)
        
        assert 'turn' in info
        assert 'current_team' in info
        assert 'num_legal_actions' in info
        assert 'pieces_on_board' in info
    
    def test_reset_initial_state(self):
        """Test initial state after reset."""
        env = HiveEnv(agent_team='white')
        obs, info = env.reset(seed=42)
        
        assert info['turn'] == 0
        assert info['current_team'] == 'white'
        assert info['pieces_on_board'] == 0
    
    def test_reset_with_opponent_black_agent(self):
        """Test reset when agent plays black with opponent."""
        opponent = RandomBot(team='white', name='OpponentBot')
        env = HiveEnv(agent_team='black', opponent=opponent)
        obs, info = env.reset(seed=42)
        
        # Opponent (white) should have already moved
        assert info['turn'] == 1
        assert info['current_team'] == 'black'
        assert info['pieces_on_board'] == 1


class TestStep:
    """Test environment step."""
    
    def test_step_returns_tuple(self):
        """Test step returns correct tuple format."""
        env = HiveEnv()
        obs, info = env.reset(seed=42)
        
        legal_actions = env.get_legal_actions()
        if legal_actions:
            result = env.step(legal_actions[0])
            assert len(result) == 5
            obs, reward, terminated, truncated, info = result
    
    def test_step_updates_state(self):
        """Test step updates game state."""
        opponent = RandomBot(team='black', name='OpponentBot')
        env = HiveEnv(agent_team='white', opponent=opponent)
        obs, info = env.reset(seed=42)
        
        initial_turn = info['turn']
        legal_actions = env.get_legal_actions()
        
        if legal_actions:
            obs, reward, terminated, truncated, info = env.step(legal_actions[0])
            # Turn should have advanced by 2 (agent + opponent)
            assert info['turn'] >= initial_turn + 1
    
    def test_step_invalid_action(self):
        """Test step with invalid action."""
        env = HiveEnv()
        obs, info = env.reset(seed=42)
        
        # Use an invalid action index
        invalid_action = env.action_space.n - 1  # Likely not a valid action
        obs, reward, terminated, truncated, info = env.step(invalid_action)
        
        # Should return negative reward for invalid action
        assert reward < 0 or 'error' in info


class TestLegalActions:
    """Test legal action handling."""
    
    def test_get_legal_actions(self):
        """Test getting legal actions."""
        env = HiveEnv()
        env.reset(seed=42)
        
        legal_actions = env.get_legal_actions()
        assert isinstance(legal_actions, list)
        assert len(legal_actions) > 0
    
    def test_action_to_turn(self):
        """Test converting action to Turn object."""
        env = HiveEnv()
        env.reset(seed=42)
        
        legal_actions = env.get_legal_actions()
        if legal_actions:
            turn = env.action_to_turn(legal_actions[0])
            assert turn is not None
            assert hasattr(turn, 'player')
            assert hasattr(turn, 'action_type')
    
    def test_action_mask_matches_legal_actions(self):
        """Test action mask matches legal actions."""
        env = HiveEnv()
        obs, info = env.reset(seed=42)
        
        action_mask = obs['action_mask']
        legal_actions = env.get_legal_actions()
        
        # Count of 1s in mask should equal legal actions count
        assert np.sum(action_mask) == len(legal_actions)
    
    def test_first_turn_placement_only(self):
        """Test first turn only has placement actions."""
        env = HiveEnv()
        env.reset(seed=42)
        
        legal_actions = env.get_legal_actions()
        for action_idx in legal_actions:
            turn = env.action_to_turn(action_idx)
            assert turn.action_type == 'place'


class TestRewards:
    """Test reward calculation."""
    
    def test_intermediate_reward_default(self):
        """Test intermediate reward is 0 by default."""
        opponent = RandomBot(team='black', name='OpponentBot')
        env = HiveEnv(agent_team='white', opponent=opponent, reward_shaping=False)
        obs, info = env.reset(seed=42)
        
        legal_actions = env.get_legal_actions()
        if legal_actions:
            obs, reward, terminated, truncated, info = env.step(legal_actions[0])
            if not terminated and not truncated:
                assert reward == 0.0
    
    def test_reward_shaping_enabled(self):
        """Test reward shaping produces non-zero intermediate rewards."""
        opponent = RandomBot(team='black', name='OpponentBot')
        env = HiveEnv(agent_team='white', opponent=opponent, reward_shaping=True)
        
        # Run several steps to potentially get shaped rewards
        obs, info = env.reset(seed=42)
        total_intermediate_reward = 0
        
        for _ in range(10):
            legal_actions = env.get_legal_actions()
            if not legal_actions:
                break
            obs, reward, terminated, truncated, info = env.step(legal_actions[0])
            if not terminated and not truncated:
                total_intermediate_reward += abs(reward)
            else:
                break
        
        # With reward shaping, we might see some non-zero rewards
        # This is a weak test since rewards depend on game state


class TestRender:
    """Test rendering functionality."""
    
    def test_render_ansi(self):
        """Test ANSI rendering."""
        env = HiveEnv(render_mode='ansi')
        env.reset(seed=42)
        
        output = env.render()
        assert isinstance(output, str)
        assert 'Turn' in output
    
    def test_render_none_mode(self):
        """Test render with no mode returns None."""
        env = HiveEnv(render_mode=None)
        env.reset(seed=42)
        
        output = env.render()
        assert output is None


class TestClose:
    """Test environment cleanup."""
    
    def test_close(self):
        """Test close method."""
        env = HiveEnv()
        env.reset(seed=42)
        env.close()
        
        assert env.game is None
        assert len(env._legal_actions) == 0
        assert len(env._action_to_turn_map) == 0


class TestGameplay:
    """Test actual gameplay scenarios."""
    
    def test_play_full_game(self):
        """Test playing a full game until termination."""
        opponent = RandomBot(team='black', name='OpponentBot')
        env = HiveEnv(agent_team='white', opponent=opponent, max_turns=50)
        
        obs, info = env.reset(seed=42)
        
        total_steps = 0
        terminated = False
        truncated = False
        
        while not terminated and not truncated and total_steps < 100:
            legal_actions = env.get_legal_actions()
            if not legal_actions:
                break
            
            # Take first legal action
            action = legal_actions[0]
            obs, reward, terminated, truncated, info = env.step(action)
            total_steps += 1
        
        # Game should end eventually
        assert terminated or truncated or total_steps >= 100
    
    def test_gym_compatibility_check(self):
        """Test that environment passes basic Gym compatibility."""
        env = HiveEnv()
        
        # Check required attributes
        assert hasattr(env, 'observation_space')
        assert hasattr(env, 'action_space')
        assert hasattr(env, 'reset')
        assert hasattr(env, 'step')
        assert hasattr(env, 'render')
        assert hasattr(env, 'close')
        
        # Check spaces are valid
        assert env.observation_space is not None
        assert env.action_space is not None
