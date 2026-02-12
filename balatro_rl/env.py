import gymnasium as gym
from gymnasium import spaces
import numpy as np
import torch
import sys
import os

# Add engine to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'engine'))

from balatro import Run, Deck, Stake, Blind, State, Voucher
from ai.encode import encode, SIZE_ENCODED
# Constants for Param lengths
from ai.encode import MAX_HAND_CARDS, MAX_JOKERS, MAX_CONSUMABLES, MAX_SHOP_CARDS, MAX_SHOP_VOUCHERS, MAX_SHOP_PACKS, MAX_PACK_ITEMS
from enum import Enum

class ActionType(Enum):
    SELECT_BLIND = 0
    SKIP_BLIND = 1
    REROLL_BOSS_BLIND = 2
    PLAY_HAND = 3
    DISCARD_HAND = 4
    CASH_OUT = 5
    MOVE_JOKER = 6
    SELL_JOKER = 7
    USE_CONSUMABLE = 8
    SELL_CONSUMABLE = 9
    BUY_SHOP_CARD = 10
    REDEEM_SHOP_VOUCHER = 11
    OPEN_SHOP_PACK = 12
    REROLL = 13
    NEXT_ROUND = 14
    CHOOSE_PACK_ITEM = 15
    SKIP_PACK = 16
    NO_OP = 17

PARAM1_LENGTH = max(MAX_HAND_CARDS, MAX_JOKERS, MAX_CONSUMABLES, MAX_SHOP_CARDS, MAX_SHOP_VOUCHERS, MAX_SHOP_PACKS, MAX_PACK_ITEMS)
PARAM2_LENGTH = max(MAX_JOKERS, 2, 1)

class BalatroGymEnv(gym.Env):
    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(self, seed=None, render_mode=None):
        super().__init__()
        self.render_mode = render_mode
        self._seed = seed
        
        # Define Action Space
        # action_type: Discrete
        # param1: MultiBinary (selection mask)
        # param2: MultiBinary (selection mask)
        self.action_space = spaces.Dict({
            "action_type": spaces.Discrete(len(ActionType)),
            "param1": spaces.MultiBinary(PARAM1_LENGTH),
            "param2": spaces.MultiBinary(PARAM2_LENGTH)
        })

        # Define Observation Space
        # The encoding is a 1D float tensor
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(SIZE_ENCODED,), dtype=np.float32
        )

        self.run = None
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._seed = seed
        
        # Initialize Game
        # Using default Deck.RED and Stake.WHITE for now, could be parameterized
        self.run = Run(Deck.RED, stake=Stake.WHITE, seed=self._seed)
        
        obs = self._get_obs()
        info = self._get_info()
        return obs, info

    def _get_obs(self):
        # encode returns a torch tensor, convert to numpy
        tensor_obs = encode(self.run)
        return tensor_obs.detach().cpu().numpy()

    def _get_info(self):
        if self.run is None:
            return {}
        return {
            "round": self.run.round,
            "ante": self.run.ante,
            "chips": self.run.round_score,
            "goal": self.run.round_goal,
            "state": self.run.state.name if self.run.state else "UNKNOWN"
        }

    def step(self, action):
        # Action is a dict
        action_type_idx = action["action_type"]
        param1_mask = action["param1"]
        param2_mask = action["param2"]

        # Convert masks to indices list for the engine
        # engine expects list of indices where mask is 1
        param1 = [i for i, x in enumerate(param1_mask) if x == 1]
        param2 = [i for i, x in enumerate(param2_mask) if x == 1]
        
        # Current logic mirrors ai/env.py _step function
        reward = -0.1 # Small penalty for existing/time step
        
        # Map indices back to ActionType
        # ActionType is an Enum, action_type_idx is int
        try:
            act_type = ActionType(action_type_idx)
        except ValueError:
             # Invalid action type
             return self._get_obs(), -10.0, False, False, {"error": "Invalid action type"}

        terminated = False
        truncated = False
        
        try:
            if act_type == ActionType.SELECT_BLIND:
                self.run.select_blind()
            elif act_type == ActionType.SKIP_BLIND:
                self.run.skip_blind()
            elif act_type == ActionType.REROLL_BOSS_BLIND:
                self.run.reroll_boss_blind()
            elif act_type == ActionType.PLAY_HAND:
                before = self.run.round_score
                self.run.play_hand(param1)
                after = self.run.round_score
                # Reward based on chip gain + bonus for clearing
                reward = (after - before) / 100.0 # Scaling
                if self.run.state == State.CASHING_OUT:
                    reward += 10.0 # Win bonus
            elif act_type == ActionType.DISCARD_HAND:
                self.run.discard(param1)
            elif act_type == ActionType.CASH_OUT:
                self.run.cash_out()
            elif act_type == ActionType.MOVE_JOKER:
                if len(param1) > 0 and len(param2) > 0:
                    self.run.move_joker(param1[0], param2[0])
            elif act_type == ActionType.SELL_JOKER:
                if len(param1) > 0:
                    self.run.sell_joker(param1[0])
            elif act_type == ActionType.USE_CONSUMABLE:
                 if len(param1) > 0:
                    self.run.use_consumable(param1[0], param2)
            elif act_type == ActionType.SELL_CONSUMABLE:
                if len(param1) > 0:
                    self.run.sell_consumable(param1[0])
            elif act_type == ActionType.BUY_SHOP_CARD:
                if len(param1) > 0:
                    # param2 for buy_shop_card is boolean (use immediately?)
                    # ai/env.py: bool(param2) -> where param2 is a list of indices.
                    # Logic: if param2 is not empty, treat as True (use it).
                    self.run.buy_shop_card(param1[0], bool(param2))
            elif act_type == ActionType.REDEEM_SHOP_VOUCHER:
                if len(param1) > 0:
                    self.run.redeem_shop_voucher(param1[0])
            elif act_type == ActionType.OPEN_SHOP_PACK:
                if len(param1) > 0:
                    self.run.open_shop_pack(param1[0])
            elif act_type == ActionType.REROLL:
                self.run.reroll()
            elif act_type == ActionType.NEXT_ROUND:
                self.run.next_round()
            elif act_type == ActionType.CHOOSE_PACK_ITEM:
                 if len(param1) > 0:
                    self.run.choose_pack_item(param1[0], param2)
            elif act_type == ActionType.SKIP_PACK:
                self.run.skip_pack()
            elif act_type == ActionType.NO_OP:
                pass
            else:
                reward = -1.0 # Unknown/Unimplemented
                
        except Exception as e:
            # Illegal move
            reward = -5.0
            # print(f"Error: {e}") 

        # Check Done
        if self.run.state == State.GAME_OVER:
            terminated = True
            if self.run.ante >= 8: # Beat the game roughly (Endless mode continues but 8 is 'win')
                 reward += 100.0
        
        obs = self._get_obs()
        info = self._get_info()
        
        return obs, reward, terminated, truncated, info

    def render(self):
        if self.run:
            print(f"Ante: {self.run.ante}, Round: {self.run.round}")
            print(f"State: {self.run.state}")
            print(f"Money: {self.run.money}, Chips: {self.run.round_score}/{self.run.round_goal}")
            if self.run.hand:
                print(f"Hand: {[str(c) for c in self.run.hand]}")
