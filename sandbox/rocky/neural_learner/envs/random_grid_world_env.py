from __future__ import print_function
from __future__ import absolute_import
from rllab.spaces import Discrete
from rllab.envs.base import Env, Step
from rllab.core.serializable import Serializable
import numpy as np
import contextlib
import random


@contextlib.contextmanager
def set_seed_tmp(seed=None):
    if seed is None:
        yield
    else:
        state = random.getstate()
        np_state = np.random.get_state()
        random.seed(seed)
        np.random.seed(seed)
        yield
        np.random.set_state(np_state)
        random.setstate(state)


def generate_maze(n_rows, n_cols, seed=None):
    with set_seed_tmp(seed):
        pass


class RandomGridWorldEnv(Env, Serializable):
    """
    'S' : starting point
    'F' or '.': free space
    'W' or 'x': wall
    'H' or 'o': hole (terminates episode)
    'G' : goal
    """

    def __init__(self, shape):
        self.shape = shape
        self.map = None

    def set_map(self, desc):
        desc = np.array(map(list, desc))
        desc[desc == '.'] = 'F'
        desc[desc == 'o'] = 'H'
        desc[desc == 'x'] = 'W'
        self.desc = desc
        self.n_row, self.n_col = desc.shape
        (start_x,), (start_y,) = np.nonzero(desc == 'S')
        self.start_state = start_x * self.n_col + start_y
        self.state = None
        self.domain_fig = None

    def regenerate_map(self):
        pass

    def reset_trial(self):
        # Reinitialize the map
        self.regenerate_map()
        return self.reset()

    def reset(self):
        self.state = self.start_state
        return self.state

    @staticmethod
    def action_from_direction(d):
        """
        Return the action corresponding to the given direction. This is a helper method for debugging and testing
        purposes.
        :return: the action index corresponding to the given direction
        """
        return dict(
            left=0,
            down=1,
            right=2,
            up=3
        )[d]

    def step(self, action):
        """
        action map:
        0: left
        1: down
        2: right
        3: up
        :param action: should be a one-hot vector encoding the action
        :return:
        """
        possible_next_states = self.get_possible_next_states(self.state, action)

        probs = [x[1] for x in possible_next_states]
        next_state_idx = np.random.choice(len(probs), p=probs)
        next_state = possible_next_states[next_state_idx][0]

        next_x = next_state / self.n_col
        next_y = next_state % self.n_col

        next_state_type = self.desc[next_x, next_y]
        if next_state_type == 'H':
            done = True
            reward = 0
        elif next_state_type in ['F', 'S']:
            done = False
            reward = 0
        elif next_state_type == 'G':
            done = True
            reward = 1
        else:
            raise NotImplementedError
        self.state = next_state
        return Step(observation=self.state, reward=reward, done=done)

    def get_possible_next_states(self, state, action):
        """
        Given the state and action, return a list of possible next states and their probabilities. Only next states
        with nonzero probabilities will be returned
        :param state: start state
        :param action: action
        :return: a list of pairs (s', p(s'|s,a))
        """
        # assert self.observation_space.contains(state)
        # assert self.action_space.contains(action)

        x = state / self.n_col
        y = state % self.n_col
        coords = np.array([x, y])

        increments = np.array([[0, -1], [1, 0], [0, 1], [-1, 0]])
        next_coords = np.clip(
            coords + increments[action],
            [0, 0],
            [self.n_row - 1, self.n_col - 1]
        )
        next_state = next_coords[0] * self.n_col + next_coords[1]
        state_type = self.desc[x, y]
        next_state_type = self.desc[next_coords[0], next_coords[1]]
        if next_state_type == 'W' or state_type == 'H' or state_type == 'G':
            return [(state, 1.)]
        else:
            return [(next_state, 1.)]

    @property
    def action_space(self):
        return Discrete(4)

    @property
    def observation_space(self):
        return Discrete(self.n_row * self.n_col)