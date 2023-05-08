import gymnasium as gym
import lanro_gym

env = gym.make('PandaStack2-v0', render=True)

obs, info = env.reset()
terminated = False
while not terminated:
    obs, reward, terminated, truncated, info = env.step(env.action_space.sample())

env.close()