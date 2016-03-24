import os.path as osp
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

from rllab import spaces
from rllab.envs.base import Step
from rllab.envs.proxy_env import ProxyEnv

from rllab.core.serializable import Serializable
from rllab.envs.mujoco.mujoco_env import MODEL_DIR, BIG
from rllab.misc.overrides import overrides


class MazeEnv(ProxyEnv, Serializable):

    MODEL_CLASS = None
    ORI_IND = None

    MAZE_HEIGHT = None
    MAZE_SIZE_SCALING = None
    MAZE_MAKE_CONTACTS = False
    MAZE_STRUCTURE = [
        [1, 1, 1, 1, 1],
        [1, 'r', 0, 0, 1],
        [1, 1, 1, 0, 1],
        [1, 'g', 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]

    def __init__(self, *args, **kwargs):

        model_cls = self.__class__.MODEL_CLASS
        if model_cls is None:
            raise "MODEL_CLASS unspecified!"
        xml_path = osp.join(MODEL_DIR, model_cls.FILE)
        tree = ET.parse(xml_path)
        worldbody = tree.find(".//worldbody")

        size_scaling = self.__class__.MAZE_SIZE_SCALING
        height = self.__class__.MAZE_HEIGHT
        structure = self.__class__.MAZE_STRUCTURE

        torso_x, torso_y = self._find_robot()

        for i in xrange(len(structure)):
            for j in xrange(len(structure[0])):
                if str(structure[i][j]) == '1':
                    # offset all coordinates so that robot starts at the origin
                    ET.SubElement(
                        worldbody, "geom",
                        name="block_%d_%d" % (i, j),
                        pos="%f %f %f" % (j*size_scaling - torso_x,
                                          i*size_scaling - torso_y,
                                          height / 2 * size_scaling),
                        size="%f %f %f" % (0.5*size_scaling,
                                           0.5*size_scaling,
                                           height/2*size_scaling),
                        type="box",
                        material="",
                        contype="1",
                        conaffinity="1",
                        rgba="0.4 0.4 0.4 1"
                    )

        torso = tree.find(".//body[@name='torso']")
        geoms = torso.findall(".//geom")
        for geom in geoms:
            if 'name' not in geom.attrib:
                raise Exception("Every geom of the torso must have a name "
                                "defined")

        if self.__class__.MAZE_MAKE_CONTACTS:
            contact = ET.SubElement(
                tree.find("."), "contact"
            )
            for i in range(len(structure)):
                for j in range(len(structure[0])):
                    if str(structure[i][j]) == '1':
                        for geom in geoms:
                            ET.SubElement(
                                contact, "pair",
                                geom1=geom.attrib["name"],
                                geom2="block_%d_%d" % (i, j)
                            )

        _, file_path = tempfile.mkstemp(text=True)
        tree.write(file_path)

        self._goal_range = self._find_goal_range()

        inner_mdp = model_cls(*args, file_path=file_path, **kwargs)
        ProxyEnv.__init__(self, inner_mdp)
        Serializable.quick_init(self, locals())

    def get_current_obs(self):
        # robot_x, robot_y = self._wrapped_env.get_body_com("torso")[:2]
        # ori = self._wrapped_env.model.data.qpos[self.__class__.ORI_IND]
        #
        # structure = self.__class__.MAZE_STRUCTURE
        # size_scaling = self.__class__.MAZE_SIZE_SCALING

        # for i in range(len(structure)):
        #     for j in range(len(structure[0])):
        #         cx = j * size_scaling
        #         cy = i * size_scaling
        #         x1 = cx - 0.5 * size_scaling
        #         x2 = cx + 0.5 * size_scaling
        #         y1 = cy - 0.5 * size_scaling
        #         y2 = cy + 0.5 * size_scaling
        #         thetas = [
        #             np.atan2(y1 - robot_y, x1 - robot_x),
        #             np.atan2(y2 - robot_y, x1 - robot_x),
        #             np.atan2(y1 - robot_y, x2 - robot_x),
        #             np.atan2(y2 - robot_y, x2 - robot_x),
        #         ]
        #
        #
        #         pass


        return np.concatenate([
            self._wrapped_env.model.data.qpos.flat,
            self._wrapped_env.model.data.qvel.flat,
            self._wrapped_env.get_body_com("torso").flat,
        ])

    def reset(self):
        ret = self.wrapped_env.reset()
        return self.get_current_obs()

    @property
    @overrides
    def observation_space(self):
        shp = self.get_current_obs().shape
        ub = BIG * np.ones(shp)
        return spaces.Box(ub*-1, ub)

    def _find_robot(self):
        structure = self.__class__.MAZE_STRUCTURE
        size_scaling = self.__class__.MAZE_SIZE_SCALING
        for i in range(len(structure)):
            for j in range(len(structure[0])):
                if structure[i][j] == 'r':
                    return j*size_scaling, i*size_scaling

    def _find_goal_range(self):
        structure = self.__class__.MAZE_STRUCTURE
        size_scaling = self.__class__.MAZE_SIZE_SCALING
        for i in xrange(len(structure)):
            for j in xrange(len(structure[0])):
                if structure[i][j] == 'g':
                    minx = j*size_scaling-size_scaling*0.5
                    maxx = j*size_scaling+size_scaling*0.5
                    miny = i*size_scaling-size_scaling*0.5
                    maxy = i*size_scaling+size_scaling*0.5
                    return minx, maxx, miny, maxy

    def step(self, action):
        _, _, done, info = self._wrapped_env.step(action)
        next_obs = self.get_current_obs()
        x, y = self._wrapped_env.get_body_com("torso")[:2]
        reward = 0
        minx, maxx, miny, maxy = self._goal_range
        if minx <= x and x <= maxx and miny <= y and y <= maxy:
            done = True
            reward = 1
        return Step(next_obs, reward, done, **info)
