from rllab.envs.base import Step
from rllab.envs.mujoco.mujoco_env import MujocoEnv
from rllab.core.serializable import Serializable
from rllab.misc.overrides import overrides
import numpy as np
import math
from rllab.mujoco_py import glfw
from rllab.mujoco_py import MjViewer


class PointEnv(MujocoEnv, Serializable):

    """
    Use Left, Right, Up, Down, A (steer left), D (steer right)
    """

    FILE = 'point.xml'

    def __init__(self, should_render=False, init_height=50, init_width=50, *args, **kwargs):
        super(PointEnv, self).__init__(*args, **kwargs)
        Serializable.quick_init(self, locals())
        self.should_render = should_render
        self.init_height = init_height
        self.init_width = init_width

    @staticmethod
    def get_reward(qpos_x, qpos_y):
        d_x = abs(qpos_x)
        d_y = abs(qpos_y)
        reward = d_x + d_y
        return -reward

    def step(self, action):
        if self.should_render is True:
            self.render()
        qpos = np.copy(self.model.data.qpos)
        qpos[2, 0] += action[1]
        ori = qpos[2, 0]
        # compute increment in each direction
        dx = math.cos(ori) * action[0]
        dy = math.sin(ori) * action[0]
        # ensure that the robot is within reasonable range
        qpos[0, 0] = np.clip(qpos[0, 0] + dx, -7, 7)
        qpos[1, 0] = np.clip(qpos[1, 0] + dy, -7, 7)
        self.model.data.qpos = qpos
        self.model.forward()
        next_obs = self.get_current_obs()
        rew = self.get_reward(qpos[0, 0], qpos[1, 0])
        return Step(next_obs, rew, False)

    def get_xy(self):
        qpos = self.model.data.qpos
        return qpos[0, 0], qpos[1, 0]

    def set_xy(self, xy):
        qpos = np.copy(self.model.data.qpos)
        qpos[0, 0] = xy[0]
        qpos[1, 0] = xy[1]
        self.model.data.qpos = qpos
        self.model.forward()

    def get_viewer(self):
        if self.viewer is None:
            self.viewer = MjViewer(init_height=self.init_height, init_width=self.init_width)
            self.viewer.start()
            self.viewer.set_model(self.model)
        return self.viewer

    @overrides
    def action_from_key(self, key):
        lb, ub = self.action_bounds
        if key == glfw.KEY_LEFT:
            return np.array([0, ub[0]*0.3])
        elif key == glfw.KEY_RIGHT:
            return np.array([0, lb[0]*0.3])
        elif key == glfw.KEY_UP:
            return np.array([ub[1], 0])
        elif key == glfw.KEY_DOWN:
            return np.array([lb[1], 0])
        else:
            return np.array([0, 0])

