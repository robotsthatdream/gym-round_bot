#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Cressot Loic
    ISIR CNRS/UPMC
    02/2018
""" 

import gym

from gym import error, spaces
from gym import utils
from gym.utils import seeding

from gym_round_bot.envs import pygletWindow
from gym_round_bot.envs import round_bot_model
from gym_round_bot.envs import round_bot_controller

import numpy as np


class RoundBotEnv(gym.Env):

    metadata = {'render.modes': ['human', 'rgb_array']}
                    
    def __init__(self):
        """
        Inits the attributes to None.        
        """        
        self.viewer = None
        self.world = None        
        self.texture = None        
        self.model = None
        self.window = None
        self.observation_space = None
        self.current_observation = None
        self.controller = None        
        self.multiview = None
        # self.action_space -> property
        self.monitor_window = None
        self.crash_stop=None
        self.reward_stop=None
        self.reward_count_stop=None
        self.reward_count=0.0
        self.normalize_observations=None
        self.normalize_rewards=None
        self.observation_transformation=None
        self.position_observations=None
        self._load() # load with loading_vars variables

    def __del__(self):
        """
        Cleans the env object before env deletion        
        """
        if self.monitor_window:
            self.delete_monitor_window()
        if self.window:
            self.window.close()

    @property
    def action_space(self):
        # self.action_space is self.controller.action_space
        return self.controller.action_space

    @property
    def compatible_worlds(self):        
        return {'rb1', # rectangle set, first person view, reward in top left corner
                'rb1_1wall', # rectangle set, first person view, reward in top left corner, middle blocks
                }

    @property
    def compatible_textures(self):        
        return {'minecraft', # minecraft game-like textures
                'colours', # uniform colors, perceptual aliasing !
                'minecraft+', # minecraft game-like textures with other additional antialiasing elements
                }

    @property
    def num_actions(self):
        return self.controller.num_actions
    
    @property
    def actions_mapping(self):
        return self.controller.actions_mapping

    def step(self, action):
        """
        Perform one step
        """
        # perform action
        self.controller.step(action)
        
        # update model and window
        if not self.position_observations :
            if not self.multiview:
                self.window.step(0.1) # update with 0.1 second intervall
                # get observation
                self.current_observation = self.window.get_image(reshape=True)
            else:
                self.window.update(0.1) # update with 0.1 second intervall
                self.current_observation = self.window.multiview_render(self.multiview, as_line=False)
        else: # observations are arrays of positions of mobable blocks
            self.window.step(0.1) # update with 0.1 second intervall
            # get observation
            self.current_observation = self.model.position_observation()

        # get reward :
        reward = self.model.current_reward
        # update self.reward_count
        self.reward_count += reward
        # check if done
        done = (self.crash_stop and reward < 0) or (self.reward_stop and reward > 0) or (self.reward_count_stop and self.reward_count <= self.reward_count_stop)

        # normalize observations if asked
        if self.normalize_observations:
            self.current_observation = self.current_observation*2.0/255.0 - 1.0 # rescale from uint8 to [-1,1] float
        # transform observations if asked :
        if self.observation_transformation:
            self.current_observation = self.observation_transformation(self.current_observation)
        # normalize observations if asked
        if self.normalize_rewards:
            reward = reward/self.model.max_reward # normalize values in [-1,1] float range
        # no info
        info={}
        return self.current_observation, reward, done, {}
        

    def reset(self):
        """
        Resets the state of the environment, returning an initial observation.
        Outputs
        -------
        observation : the initial observation of the space. (Initial reward is assumed to be 0.)
        """
        self.model.reset()
        self.reward_count=0.0
        if not self.position_observations:
            self.current_observation = self.window.get_image(reshape=True)#get image as a numpy line
        else:
            self.current_observation = self.model.position_observation()

        # normalize observations if asked
        if self.normalize_observations:
            self.current_observation = self.current_observation*2.0/255.0 - 1.0 # rescale from uint8 to [-1,1] float
        # transform observations if asked :
        if self.observation_transformation:
            self.current_observation = self.observation_transformation(self.current_observation)
      
        return self.current_observation
        

    def render(self, mode='human', close=False):

        if mode == 'rgb_array':
            # reshape as line
            return self.current_observation
        elif mode == 'human':
            # this slows down rendering with a factor 10 !
            # TODO : show current observation on screen (potentially fusionned image, and not only last render !)
            if not self.window.visible:
                self.window.set_visible(True)
        else: 
            raise Exception('Unknown render mode: '+mode)


    def seed(self, seed=None):
        seed = seeding.np_random(seed)
        return [seed]

    def _load(self):
        """
        Loads a world into environnement with metadata vars

        Parameters used in metadata for loading :
            -> see in load_metada method
        """
        metadata = RoundBotEnv.metadata
        if not metadata['world'] in self.compatible_worlds:
            raise(Exception('Error: unknown or uncompatible world \'' + metadata['world'] + '\' for environnement round_bot'))
        if not metadata['texture'] in self.compatible_textures:
            raise(Exception('Error: unknown or uncompatible texture \'' + metadata['texture'] + '\' for environnement round_bot'))
        
        ## shared settings
        self.world = metadata['world']
        self.texture = metadata['texture']
        self.random_start = metadata['random_start']
        random_start_rot = ('Theta' in metadata['controller'].controllerType)
        self.model = round_bot_model.Model(world=metadata['world'], random_start_pos=self.random_start, random_start_rot=random_start_rot, texture=metadata['texture'])
        self.obssize = metadata['obssize']
        self.crash_stop = metadata['crash_stop']
        self.reward_count_stop = metadata['reward_count_stop']
        self.reward_stop = metadata['reward_stop']

        # save controller and plug it to model :
        self.controller = metadata['controller']
        self.controller.model = self.model
        self.normalize_rewards = metadata['normalize_rewards']     
        self.normalize_observations = metadata['normalize_observations']     
        self.observation_transformation = metadata['observation_transformation']     
        self.position_observations = metadata['position_observations']

        shape = self.obssize
        self.obs_dim = shape[0]*shape[1]*3


        # build main window
        self.window = pygletWindow.MainWindow(  self.model,
                                                global_pov=metadata['global_pov'],
                                                perspective = metadata['perspective'],
                                                interactive=False,
                                                focal=metadata['focal'],
                                                width=metadata['obssize'][0],
                                                height=metadata['obssize'][1],
                                                caption='Round bot in '+self.world+' world',
                                                resizable=False,
                                                visible=metadata['visible']
                                                )

        # build secondary observation window if asked
        if metadata['winsize']:
            self.monitor_window = pygletWindow.SecondaryWindow(self.model,
                                                    global_pov = True,
                                                    perspective = False,
                                                    width=metadata['winsize'][0],
                                                    height=metadata['winsize'][1],
                                                    caption='Observation window '+ self.world,
                                                    resizable=False,
                                                    visible=True,
                                                    )           
            # plug monitor_window to window
            self.window.add_follower(self.monitor_window)

        # observation are RGB images of rendered world (as line arrays)
        self.observation_space = spaces.Box(low=0, high=255, shape=[1, metadata['obssize'][0]*metadata['obssize'][1]*3],dtype=np.uint8)

        self.multiview = metadata['multiview'] # if not None, observations will be fusion of subjective view with given relative xOz angles

    def message(self, message):
        """
        Get message from training and use it if possible
        """
        if self.monitor_window:
            self.monitor_window.message = message

    def add_monitor_window(self, height, width):
        """
        adds a monitor window if there are none yet
        """
        if not (height > 0 and width > 0):
            raise Exception('unvalid dimensions for monitor window')
        if not self.monitor_window:
            self.monitor_window = pygletWindow.SecondaryWindow(
                                        self.model,
                                        global_pov = True,
                                        perspective = False,
                                        width=height,
                                        height=width,
                                        caption='Observation window '+ self.world,
                                        resizable=False,
                                        visible=True,
                                        )           
            # plug monitor_window to window
            self.window.add_follower(self.monitor_window)
        else:
            raise Warning('a monitor window has already been added !')

    def delete_monitor_window(self):
        """
        deletes the monitor window
        """
        if not self.monitor_window:
            raise Warning('no monitor window to delete')
        else:
            self.window.remove_follower(self.monitor_window)
            self.monitor_window.close()
            del self.monitor_window
            self.monitor_window = None


def set_metadata(world='rb1',
                texture='minecraft',
                controller=round_bot_controller.make(name='Theta',dtheta=20,speed=10,int_actions=False,xzrange=2,thetarange=2),
                obssize=[16,16],
                winsize=None,
                global_pov=None,
                perspective=True,
                visible=False,
                multiview=None,
                focal=65.0,
                crash_stop=False,
                reward_stop=False,
                reward_count_stop = -10,
                random_start=True,
                normalize_observations=False,
                normalize_rewards=False,
                observation_transformation = None,
                position_observations = False,
                ):
    """ static module method for setting loading variables before call to gym.make

        parameters :
        -----------
        - world : (str) name of the world to load
        - texture : (str) name of texture to set to world brick blocks
        - controller: (round_bot_Controller) controller object to use for mapping from actions to robot control
        - obssize / winsize : (tuple(int)) observation's / monitor windows's size tuple
        - global_pov : (Tuple(float,float,float) or Bool or None) global point of view tuple.
            Set True for automatic computing and None if none
        - perspective : (Bool) If True, perspective is projective, else it is orthogonal
        - visible : (Bool) If True the main window will be shown (slows down rendering)
        - multiview : List(float) List of angles for multi-view rendering. The renders will be fusioned into one image.
        - focal : float (<180°) The camera focal
        - crash_stop : (Bool) Wether to stop when crashing in a wall with negative reward (for speeding dqn learning for instance)            
        - reward_count_stop: (int or False) If not False, stop when the sum of rewards (before normalization) reaches this value.
        - reward_stop : (Bool) Wether to stop when reaching positive reward            
        - random_start : (Bool) Randomly start from start positions or not
        - normalize_observations : (Bool) Rescale observations from (int)[0:255] range to (float)[-1:1] with X -> X * 2.0/255 -1.0
        - normalize_rewards : (Bool) Rescale rewards to (float)[-1:1] range by dividing rewards by world's highest abs reward value
        - observation_transformation : (function) apply observation_transformation function to observations after normalization
        - position_observations: (Bool) observations are not images (np.array([w,h,c])) but [X, Y, Z, rx, ry, rz] np.arrays of 
            every moving blocks in the scene
    """
    RoundBotEnv.metadata['world'] = world
    RoundBotEnv.metadata['texture'] = texture
    RoundBotEnv.metadata['controller'] = controller
    RoundBotEnv.metadata['obssize'] = obssize
    RoundBotEnv.metadata['winsize'] = winsize
    RoundBotEnv.metadata['global_pov'] = global_pov
    RoundBotEnv.metadata['perspective'] = perspective # 
    RoundBotEnv.metadata['visible'] = visible
    RoundBotEnv.metadata['multiview'] = multiview
    RoundBotEnv.metadata['focal'] = focal
    RoundBotEnv.metadata['crash_stop'] = crash_stop
    RoundBotEnv.metadata['reward_count_stop'] = reward_count_stop
    RoundBotEnv.metadata['reward_stop'] = reward_stop
    RoundBotEnv.metadata['random_start'] = random_start
    RoundBotEnv.metadata['normalize_observations'] = normalize_observations
    RoundBotEnv.metadata['normalize_rewards'] = normalize_rewards
    RoundBotEnv.metadata['observation_transformation'] = observation_transformation
    RoundBotEnv.metadata['position_observations'] = position_observations

    

set_metadata() # loading with default values
