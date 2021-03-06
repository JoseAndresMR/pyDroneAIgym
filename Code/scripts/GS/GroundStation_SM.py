#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------------------------------------------------
# ROS-MAGNA
# ----------------------------------------------------------------------------------------------------------------------
# The MIT License (MIT)

# Copyright (c) 2016 GRVC University of Seville

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# ----------------------------------------------------------------------------------------------------------------------

"""
Created on Mon Feb 21 2018

@author: josmilrom
"""

from smach import StateMachine, State, CBState, cb_interface,Concurrence, Sequence
import smach_ros, rospy
import time
from smach_ros import SimpleActionState
import numpy as np
import tf
import json
import copy
from geometry_msgs.msg import PoseStamped

from magna.msg import *

class GroundStation_SM(object):
    # At init, the State Machine receives as "heritage" the hole "self" of GS
    def __init__(self,heritage):
        # Creation of State Machine and definition of its outcomes
        self.gs_sm = StateMachine(outcomes=['completed', 'failed'])

        with self.gs_sm:
            # Initialization of id, number of waypoints and target
            self.DictionarizeCBStateCallbacks()
            self.DictionarizeSASCallbacks()
            self.DictionarizeCCRCallbacks()

            # For every entity in sm defining steps list, call function to add the step to sm
            for mission_part_def in heritage.mission_def["State_Machine"]:
                self.add_sm_from_CSV(self.gs_sm,mission_part_def,{},heritage)

            # If flag to view the sm is arised, start the introspector
            if heritage.smach_view == True:
                sis = smach_ros.IntrospectionServer('magna/GS_introspection', self.gs_sm, '/GS')
                sis.start()

    # Function to add to current State Machine depending on step in sm defining steps list
    def add_sm_from_CSV(self, sm, mission_part_def, parent_params, heritage):

        # Selection depending on step value. Completed ouput is next step value.
        # For single states, check callback

        if mission_part_def["type"] == "CBState":
            
            cb_kwargs = {'heritage' : heritage, "parameters" : {}}

            if "parameters" in mission_part_def.keys():
                # cb_kwargs.update(mission_part_def["parameters"])
                cb_kwargs["parameters"] = mission_part_def["parameters"]

            if "ids_var" in mission_part_def.keys():
                mission_part_def = self.IdsExtractor(mission_part_def,heritage)
                cb_kwargs["parameters"].update({"agents_list":mission_part_def["ids"]})

            sm.add(mission_part_def["name"],
                             CBState(self.CBStateCBDic[mission_part_def["state_type"]],
                                cb_kwargs=cb_kwargs),
                             mission_part_def["outcomes"])

        elif mission_part_def["type"] == "SimpleActionState":

            if "outcomes" not in mission_part_def.keys():
                mission_part_def["outcomes"] = None

            mission_part_def = self.IdsExtractor(mission_part_def,heritage)

            for ids in mission_part_def["ids"]:

                params = self.UpdateLocalParameters(ids,mission_part_def,parent_params)

                params.update({'heritage' : heritage})
                params["id"] = ids
                
                self.params = params        ### AHORRARME SELF

                sm.add('{0}_{1}'.format(ids,mission_part_def["name"]),
                        SimpleActionState('/magna/GS_Agent_{0}/{1}_command'.format(params["agent"],mission_part_def["state_type"]),
                                            self.SASMsgTypeDic[mission_part_def["state_type"]],
                                            goal_cb=self.SASGoalCBDic[mission_part_def["state_type"]],
                                            result_cb=self.SASResultCBDic[mission_part_def["state_type"]],
                                            input_keys=['params'],
                                            output_keys=['id','n_wp'],
                                            goal_cb_kwargs={"params" : self.params},
                                            result_cb_kwargs={"heritage":heritage},
                                            outcomes=['succeeded','collision','low_battery','GS_critical_event','utm_new_flightplan']),
                        mission_part_def["outcomes"])


        elif mission_part_def["type"] == "StateMachine":

            mission_part_def = self.IdsExtractor(mission_part_def,heritage)

            for ids in mission_part_def["ids"]:
                # self.id = ids

                params = self.UpdateLocalParameters(ids,mission_part_def,parent_params)

                new_sm = StateMachine(outcomes=mission_part_def["outcomes"].keys(),
                                                        input_keys=[])

                with new_sm:

                    for occurrence in mission_part_def["occurrencies"]:

                        self.add_sm_from_CSV(new_sm,occurrence,params,heritage)

                # concurrence = Concurrence(input_keys = [],
                #         output_keys = [],
                #         default_outcome = 'completed',
                #         outcome_map = {})


                sm.add('{0}_{1}'.format(ids,mission_part_def["name"]), new_sm, mission_part_def["outcomes"])




        elif mission_part_def["type"] == "Concurrence":

            mission_part_def = self.IdsExtractor(mission_part_def,heritage)

            for ids in mission_part_def["ids"]:
                # self.id = ids

                params = self.UpdateLocalParameters(ids,mission_part_def,parent_params)

                if "child_termination_cb" not in mission_part_def.keys():
                    child_termination_cb = None
                else:
                    child_termination_cb = self.CCR_CT_Dic[mission_part_def["child_termination_cb"]]

                if "outcome_cb" not in mission_part_def.keys():
                    outcome_cb = None
                else:
                    outcome_cb = self.CCR_O_Dic[mission_part_def["outcome_cb"]]

                concurrence = Concurrence(outcomes=mission_part_def["outcomes"].keys(),
                                        input_keys = [],
                                        output_keys = [],
                                        default_outcome = 'completed',
                                        outcome_map = {},
                                        outcome_cb = outcome_cb,
                                        child_termination_cb = child_termination_cb)

                with concurrence:
                    for occurrence in mission_part_def["occurrencies"]:

                        self.add_sm_from_CSV(concurrence,occurrence,params,heritage)


                for outcome in  mission_part_def["occurrencies_outcome_map"].keys():
                    for state in mission_part_def["occurrencies_outcome_map"][outcome].keys():
                        outcome_dict = mission_part_def["occurrencies_outcome_map"][outcome]

                        if type(state) == list:
                            for i in state:
                                outcome_dict[i] = outcome_dict[state]

                            del outcome_dict[state]

                        elif state == "all":
                            for occurrency in mission_part_def["occurrencies"]:
                                if type(occurrency["ids"]) == int:
                                    outcome_dict['{0}_{1}'.format(occurrency["ids"],occurrency["name"])] = outcome_dict[state]

                                elif type(occurrency["ids"]) == list:
                                    for occurency_ids in occurrency["ids"]:
                                        outcome_dict['{0}_{1}'.format(occurency_ids,occurrency["name"])] = outcome_dict[state]

                            del outcome_dict[state]

                concurrence._outcome_map = mission_part_def["occurrencies_outcome_map"]

                if "outcomes" not in mission_part_def.keys():
                    mission_part_def["outcomes"] = None

                sm.add('{0}_{1}'.format(ids,mission_part_def["name"]),
                        concurrence,
                        transitions = mission_part_def["outcomes"])


        elif mission_part_def["type"] == "Sequence":

            mission_part_def = self.IdsExtractor(mission_part_def,heritage)

            for ids in mission_part_def["ids"]:

                params = self.UpdateLocalParameters(ids,mission_part_def,parent_params)

                sequence = Sequence(outcomes = mission_part_def["outcomes"].keys(),
                                    connector_outcome = mission_part_def["connector_outcome"])

                with sequence:
                    for occurrence in mission_part_def["occurrencies"]:

                        self.add_sm_from_CSV(sequence,occurrence,params,heritage)

                sm.add('{0}_{1}'.format(ids,mission_part_def["name"]),
                            sequence,
                            transitions = mission_part_def["outcomes"])


    #### STATE CALLBACKS ####

    # State callback to create a new world
    @cb_interface(outcomes=['completed','failed'])
    def world_config_stcb(self,heritage,parameters = {}):
        
        outcome = heritage.worldConfig(parameters)

        return outcome

    # State callback to wait one second. In future will fuse with next callback
    @cb_interface(outcomes=['completed','failed'])
    def wait_stcb(self,heritage,parameters = {}):

        parameters.setdefault("duration", 0)

        outcome = heritage.wait(parameters["exit_type"],parameters["duration"])

        return outcome

    @cb_interface(outcomes=['completed','failed'])
    def save_csv_stcb(self,heritage,parameters = {}):

        outcome = heritage.sendNotificationsToAgents(parameters["agents_list"],"save_csv")

        return outcome

    @cb_interface(outcomes=['completed','failed'])
    def algorithm_control_stcb(self,heritage,parameters = {}):

        parameters.setdefault("action", "delete"), parameters.setdefault("params", []), parameters.setdefault("values", [])

        outcome = heritage.AlgorithmControlCommand(parameters["agents_list"],parameters["name"], parameters["action"],parameters["params"], parameters["values"])

        return outcome

    # State callback to spawn Agents
    @cb_interface(outcomes=['completed','failed'])
    def spawn_agents_stcb(self,heritage,parameters = {}):

        outcome = heritage.SpawnAgents(parameters["initial_poses"])

        return outcome

    def DictionarizeCBStateCallbacks(self):
        self.CBStateCBDic = {}
        self.CBStateCBDic["world_config"] = self.world_config_stcb
        self.CBStateCBDic["spawn_agents"] = self.spawn_agents_stcb
        self.CBStateCBDic["wait"] = self.wait_stcb
        self.CBStateCBDic["save_csv"] = self.save_csv_stcb
        self.CBStateCBDic["algorithm_control"] = self.algorithm_control_stcb

    #### ACTIONS CALLBACKS ####

    # Goal callback for takeoff state service
    def take_off_goal_cb(self, ud, goal, params):

        goal.height = float(params["height"])     # Define takeoff height, in future will be received in ud or mission dictionary
        # time.sleep(3*ud.id)
        return goal

    # Result callback for takeoff state service
    def take_off_result_cb(self, ud, status, result):
        return "succeeded"

    # Goal callback for basic move service
    def basic_move_goal_cb(self, ud, goal, params):
        goal.move_type = params["move_type"]
        goal.dynamic = params["dynamic"]
        goal.direction = params["direction"]
        goal.value = params["value"]
        goal.duration = params["duration"]

        return goal

    # Result callback for basic move service
    def basic_move_result_cb(self, ud, status, result):
        return "succeeded"

    # Goal callback for set mission service
    def set_mission_goal_cb(self, ud, goal, params):

        goal.poses_list = np.array([])
        for path_part in params["path"]:
            goal.poses_list = np.append(goal.poses_list,
                                                np.array(params["heritage"].MakePath(path_part["definition"],params["id"])))
        goal.include_takeoff = False
        if "include_takeoff" in params.keys():
            goal.smooth_path_mode = params["include_takeoff"]

        goal.include_land = False
        if "include_land" in params.keys():
            goal.dynamic = params["include_land"]
    
        return goal

    # Result callback for set mission service. In the future should be implemented out of SM
    def set_mission_result_cb(self, ud, status, result):

        return result.output

    # Goal callback for follow path service
    def follow_path_goal_cb(self, ud, goal, params):

        
        goal.goal_path_poses_list = np.array([])
        if params["path"] == "from utm":

            goal.goal_path_poses_list = np.array(params["heritage"].utm_flightplan_list[params["id"]-1])

        else:
            for path_part in params["path"]:
                goal.goal_path_poses_list = np.append(goal.goal_path_poses_list,
                                                        np.array(params["heritage"].MakePath(path_part["definition"],params["id"])))
        
        goal.smooth_path_mode = 0
        if "smooth_path_mode" in params.keys():
            goal.smooth_path_mode = params["smooth_path_mode"]

        goal.dynamic = "velocity"
        if "dynamic" in params.keys():
            goal.dynamic = params["dynamic"]

        goal.duration = 0.0
        if "duration" in params.keys():
            goal.duration = params["duration"]        

        return goal

    # Result callback for follow path service. In the future should be implemented out of SM
    def follow_path_result_cb(self, ud, status, result):

        return result.output


    # Goal callback for follow agent ad service
    def follow_agent_ad_goal_cb(self, ud, goal, params):
        # Build the goal from arguments
        goal.target_ID = params["target_ID"]
        goal.distance = params["distance"]
        goal.duration = params["duration"]

        return goal

    # Result callback for follow agent ad service
    def follow_agent_ad_result_cb(self, ud, status, result):
        return result.output

    # Goal callback for follow agent ap service
    def follow_agent_ap_goal_cb(self, ud, goal, params):
        # Build the goal from arguments
        goal.target_ID = params["target_ID"]
        goal.pos = params["pos"]
        goal.duration = params["duration"]      # In the future should be received from argument or mission dictionary

        return goal

    # Result callback for follow agent ap service
    def follow_agent_ap_result_cb(self, ud, status, result):
        return result.output

    # Goal callback for land service
    def land_goal_cb(self, ud, goal, params):
        goal.something = True       # In the future should disappear

        return goal

    # Result callback for land service
    def land_result_cb(self, ud, status,result):
        return "succeeded"


    def DictionarizeSASCallbacks(self):

        self.SASGoalCBDic = {}
        self.SASGoalCBDic["take_off"] = self.take_off_goal_cb
        self.SASGoalCBDic["basic_move"] = self.basic_move_goal_cb
        self.SASGoalCBDic["follow_path"] = self.follow_path_goal_cb
        self.SASGoalCBDic["follow_agent_ad"] = self.follow_agent_ad_goal_cb
        self.SASGoalCBDic["follow_agent_ap"] = self.follow_agent_ap_goal_cb
        self.SASGoalCBDic["land"] = self.land_goal_cb
        self.SASGoalCBDic["set_mission"] = self.set_mission_goal_cb

        self.SASResultCBDic = {}
        self.SASResultCBDic["take_off"] = self.take_off_result_cb
        self.SASResultCBDic["basic_move"] = self.basic_move_result_cb
        self.SASResultCBDic["follow_path"] = self.follow_path_result_cb
        self.SASResultCBDic["follow_agent_ad"] = self.follow_agent_ad_result_cb
        self.SASResultCBDic["follow_agent_ap"] = self.follow_agent_ap_result_cb
        self.SASResultCBDic["land"] = self.land_result_cb
        self.SASResultCBDic["set_mission"] = self.set_mission_result_cb

        self.SASMsgTypeDic = {}
        self.SASMsgTypeDic["take_off"] = TakeOffAction
        self.SASMsgTypeDic["basic_move"] = BasicMoveAction
        self.SASMsgTypeDic["follow_path"] = FollowPathAction
        self.SASMsgTypeDic["follow_agent_ad"] = FollowAgentADAction
        self.SASMsgTypeDic["follow_agent_ap"] = FollowAgentAPAction
        self.SASMsgTypeDic["land"] = LandAction
        self.SASMsgTypeDic["set_mission"] = SetMissionAction

        self.SASGoalDic = {}
        self.SASGoalDic["take_off"] = TakeOffGoal
        self.SASGoalDic["basic_move"] = BasicMoveGoal
        self.SASGoalDic["follow_path"] = FollowPathGoal
        self.SASGoalDic["follow_agent_ad"] = FollowAgentADGoal
        self.SASGoalDic["follow_agent_ap"] = FollowAgentAPGoal
        self.SASGoalDic["land"] = LandGoal
        self.SASGoalDic["set_mission"] = SetMissionGoal


    #### CONCURRENCE OUTCOMES CALLBACKS ####

    def preempt_all_at_one_collision_child_termination_cb(self,actual_outcomes_map):

        for outcome in actual_outcomes_map.values():
            if outcome == "collision":
                return True

        return False

    def outcome_collision_if_any_collided_outcome_cb(self,final_outcomes_map):
        if any("collision" in s for s in final_outcomes_map.values()):
            return "collision"

        else:
            return None

    def DictionarizeCCRCallbacks(self):

        self.CCR_CT_Dic = {}
        self.CCR_CT_Dic["all_at_one_collision"] = self.preempt_all_at_one_collision_child_termination_cb

        self.CCR_O_Dic = {}
        self.CCR_O_Dic["collision_if_any_collided"] = self.outcome_collision_if_any_collided_outcome_cb


    #### Miscellaneous ####
    #     
    def IdsExtractor(self,mission_part_def,heritage):

        if type(mission_part_def["ids"]) == int:
            ids = [mission_part_def["ids"]]

        elif type(mission_part_def["ids"]) == list:
            ids = mission_part_def["ids"]

        elif mission_part_def["ids"] == "all":

            if mission_part_def["ids_var"] == "agent":
                ids = range(1, heritage.N_agents + 1)

            elif mission_part_def["ids_var"] == "wp":
                ids = range(1, len(mission_part_def["params"]["path"]) + 1)

        mission_part_def["ids"] = ids

        return mission_part_def


    def UpdateLocalParameters(self,ids,mission_part_def,parent_params):

        params = copy.deepcopy(parent_params)
        if "parameters" in mission_part_def.keys():
            params.update(mission_part_def["parameters"])

        if "ids_var" in mission_part_def.keys():
            params.update({mission_part_def["ids_var"] : ids})

        return params