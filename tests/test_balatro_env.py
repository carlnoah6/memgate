import sys
import os
import numpy as np

# Ensure balatro_rl is in path
sys.path.append(os.getcwd())

from balatro_rl.env import BalatroGymEnv

def test_environment():
    print("Initializing environment...")
    env = BalatroGymEnv()
    
    print("Action Space:", env.action_space)
    print("Observation Space:", env.observation_space)
    
    obs, info = env.reset(seed=42)
    print("Initial Observation Shape:", obs.shape)
    print("Initial Info:", info)
    
    # Check observation shape matches space
    assert env.observation_space.contains(obs), "Observation not in space!"
    
    print("\nRunning random agent for 1000 steps...")
    
    terminated = False
    truncated = False
    total_reward = 0
    steps = 0
    
    while steps < 1000:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1
        
        if steps % 100 == 0:
            print(f"Step {steps}: Reward={reward:.2f}, State={info.get('state')}")
            
        if terminated or truncated:
            print(f"Episode finished at step {steps} with total reward {total_reward:.2f}")
            obs, info = env.reset()
            terminated = False
            truncated = False
            total_reward = 0
            
    print("\nTest passed! Environment is runnable.")

if __name__ == "__main__":
    test_environment()
