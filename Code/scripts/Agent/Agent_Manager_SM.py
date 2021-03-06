#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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

from smach import StateMachine, State, CBState, cb_interface
import smach_ros
import rospy, time
from smach_ros import ActionServerWrapper

from magna.msg import *

class Agent_Manager_SM(object):
    # At init, the State Machine receives as "heriage" the hole "self" of the Ground Station
    def __init__(self,heritage):
        # Creation of State Machine and definition of its outcomes
        self.agent_sm = StateMachine(outcomes=['completed', 'failed'])

        with self.agent_sm:
            # Initialization of the dictionary containing every Action Service Wrapper
            self.asw_dicc = {}

            ### ACTION SERVER ADVERTISING ###

            # Add a state where drone does nothing but wait to receive a service order
            StateMachine.add('action_server_advertiser',
                            CBState(self.action_server_advertiser_stcb,
                                         cb_kwargs={'heritage':heritage,'asw_dicc':self.asw_dicc}),
                            {'completed':'completed'})

            # Every action service wrapper is similar following a structure defined by SMACH.
            # Each wrapper is defined and added to
            # To understand what they do, see callbacks below

            ### TAKE-OFF STATE MACHINE & WRAPPER ###

            self.take_off_sm = StateMachine(outcomes=['completed', 'failed'],
                                         input_keys=['action_goal'])

            self.asw_dicc['take_off'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/take_off_command'.format(heritage.ID),
                        TakeOffAction,
                        self.take_off_sm,
                        ['completed'], ['failed'], ['preempted'],
                        goal_key = 'action_goal',
                        result_key = 'action_result' )

            with self.take_off_sm:

                StateMachine.add('take_off',
                                 CBState(self.take_off_stcb,
                                         input_keys=['action_goal'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed'})

            ### LAND STATE MACHINE & WRAPPER ###

            self.land_sm = StateMachine(outcomes=['completed', 'failed'],
                                         input_keys=['action_goal'])

            self.asw_dicc['land'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/land_command'.format(heritage.ID),
                        LandAction,
                        self.land_sm,
                        ['completed'], ['failed'], ['preempted'],
                        goal_key = 'action_goal',
                        result_key = 'action_result' )

            with self.land_sm:

                StateMachine.add('land',
                                 CBState(self.land_stcb,
                                         input_keys=['action_goal'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed'})


            ### BASIC MOVE STATE MACHINE & WRAPPER ###

            self.basic_move_sm = StateMachine(outcomes=['completed', 'failed','collision','low_battery','GS_critical_event'],
                                         input_keys=['action_goal','action_result'])

            self.asw_dicc['basic_move'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/basic_move_command'.format(heritage.ID),
                        BasicMoveAction,
                        self.basic_move_sm,
                        ['completed'], ['failed'],['collision','low_battery','GS_critical_event'],
                        goal_key = 'action_goal',
                        result_key = 'action_result' )

            with self.basic_move_sm:

                StateMachine.add('basic_move',
                                 CBState(self.basic_move_stcb,
                                         input_keys=['action_goal','action_result'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed',
                                  'collision':'collision',
                                  'low_battery':'low_battery',
                                  'GS_critical_event':'GS_critical_event'})

            ### SET MISSION STATE MACHINE & WRAPPER ###
            self.set_mission_sm = StateMachine(outcomes=['completed', 'failed','collision','low_battery','GS_critical_event'],
                                         input_keys=['action_goal','action_result'])

            self.asw_dicc['set_mission'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/set_mission_command'.format(heritage.ID),
                        SetMissionAction,
                        self.set_mission_sm,
                        ['completed'], ['failed'], ['collision','low_battery','GS_critical_event'],
                        goal_key = 'action_goal',
                        result_key = 'action_result'
                        )

            with self.set_mission_sm:

                StateMachine.add('set_mission',
                                 CBState(self.set_mission_stcb,
                                         input_keys=['action_goal','action_result','_preempt_requested'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed',
                                  'collision':'collision',
                                  'low_battery':'low_battery',
                                  'GS_critical_event':'GS_critical_event'})

            ### FOLLOW PATH STATE MACHINE & WRAPPER ###
            self.follow_path_sm = StateMachine(outcomes=['completed', 'failed','collision','low_battery','GS_critical_event'],
                                         input_keys=['action_goal','action_result'])

            self.asw_dicc['follow_path'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/follow_path_command'.format(heritage.ID),
                        FollowPathAction,
                        self.follow_path_sm,
                        ['completed'], ['failed'], ['collision','low_battery','GS_critical_event'],
                        goal_key = 'action_goal',
                        result_key = 'action_result'
                        )

            with self.follow_path_sm:

                StateMachine.add('follow_path',
                                 CBState(self.follow_path_stcb,
                                         input_keys=['action_goal','action_result','_preempt_requested'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed',
                                  'collision':'collision',
                                  'low_battery':'low_battery',
                                  'GS_critical_event':'GS_critical_event'})

            # StateMachine.add('to_wp', self.follow_path_sm,
            #                         {'completed':'action_server_advertiser'})

            ### FOLLOW Agent AD STATE MACHINE  & WRAPPER###
            self.follow_agent_ad_sm = StateMachine(outcomes=['completed', 'failed','collision','low_battery','GS_critical_event'],
                                         input_keys=['action_goal','action_result'])

            self.asw_dicc['follow_agent_ad'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/follow_agent_ad_command'.format(heritage.ID),
                        FollowAgentADAction,
                        self.follow_agent_ad_sm,
                        ['completed'], ['failed'], ['collision','low_battery','GS_critical_event'],
                        goal_key = 'action_goal',
                        result_key = 'action_result' )

            with self.follow_agent_ad_sm:

                StateMachine.add('follow_agent_ad',
                                 CBState(self.follow_agent_ad_stcb,
                                         input_keys=['action_goal','action_result','_preempt_requested'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed',
                                  'collision':'collision',
                                  'low_battery':'low_battery',
                                  'GS_critical_event':'GS_critical_event'})

            ### FOLLOW Agent AP STATE MACHINE  & WRAPPER###
            self.follow_agent_ap_sm = StateMachine(outcomes=['completed', 'failed','collision','low_battery','GS_critical_event'],
                                         input_keys=['action_goal','action_result'])

            self.asw_dicc['follow_agent_ap'] = ActionServerWrapper(
                        '/magna/GS_Agent_{}/follow_agent_ap_command'.format(heritage.ID),
                        FollowAgentAPAction,
                        self.follow_agent_ap_sm,
                        ['completed'], ['failed'], ['collision','low_battery','GS_critical_event'],
                        goal_key = 'action_goal',
                        result_key = 'action_result' )

            with self.follow_agent_ap_sm:

                StateMachine.add('follow_agent_ap',
                                 CBState(self.follow_agent_ap_stcb,
                                         input_keys=['action_goal','action_result','_preempt_requested'],
                                         cb_kwargs={'heritage':heritage}),
                                 {'completed':'completed',
                                  'collision':'collision',
                                  'low_battery':'low_battery',
                                  'GS_critical_event':'GS_critical_event'})

            if heritage.smach_view == True:
                sis = smach_ros.IntrospectionServer('magna/Agent_{}_introspection'.format(heritage.ID), self.agent_sm, '/Agent_{}'.format(heritage.ID))
                sis.start()

    #### STATE CALLBACKS ####

    @cb_interface(outcomes=['completed', 'failed'])
    def action_server_advertiser_stcb(self, heritage, asw_dicc):
        heritage.SetVelocityCommand(True)       # Tell GS to hover while no server request is received
        for key in asw_dicc.keys():     # Run every ASW stored
            asw_dicc[key].run_server()

        # Function to inform Ground Station about actual Agent's state
        heritage.state = "waiting for action command"
        heritage.GSStateActualization()

        time.sleep(0.2)

        rospy.spin()

        return 'completed'

    @cb_interface(outcomes=['completed','failed'])
    def take_off_stcb(self,heritage):
        outcome = heritage.TakeOffCommand(self.action_goal.height,True)     # Tell GS to take off

        return outcome

    @cb_interface(outcomes=['completed','failed','collision','low_battery','GS_critical_event'])
    def set_mission_stcb(self,heritage):

        # Copy the goal path to follow into GS's variable
        poses_list = self.action_goal.poses_list
        include_takeoff = self.action_goal.include_takeoff
        include_land = self.action_goal.include_land
        output = heritage.CreateMission(poses_list,include_takeoff,include_land)     # Tell the GS to execute that function

        self.action_result.output = output

        return 'completed'

    @cb_interface(outcomes=['completed','failed','collision','low_battery','GS_critical_event'])
    def follow_path_stcb(self,heritage):

        # Copy the goal path to follow into GS's variable
        heritage.smooth_path_mode = self.action_goal.smooth_path_mode
        heritage.goal_path_poses_list = self.action_goal.goal_path_poses_list
        output = heritage.PathFollower(self.action_goal.dynamic,self.action_goal.duration)     # Tell the GS to execute that function

        self.action_result.output = output

        return 'completed'

    @cb_interface(outcomes=['completed','failed','collision','low_battery','GS_critical_event'])
    def follow_agent_ad_stcb(self,heritage):

        # Tell the GS to execute AgentFollowerAD role with at the required distance
        output = heritage.AgentFollowerAtDistance(self.action_goal.target_ID,self.action_goal.distance,self.action_goal.duration)

        self.action_result.output = output

        return 'completed'

    @cb_interface(outcomes=['completed','failed','collision','low_battery','GS_critical_event'])
    def follow_agent_ap_stcb(self,heritage):

        # Tell the GS to execute AgentFollowerAP role with the required bias
        output = heritage.AgentFollowerAtPosition(self.action_goal.target_ID,self.action_goal.pos,self.action_goal.duration)

        self.action_result.output = output

        return 'completed'


    @cb_interface(outcomes=['completed','failed'])
    def land_stcb(self,heritage):

        outcome = heritage.LandCommand(True)        # Tell the GS to land

        return outcome

    @cb_interface(outcomes=['completed','failed','collision','low_battery','GS_critical_event'])
    def basic_move_stcb(self,heritage):

        # Parse received basic move information
        move_type = self.action_goal.move_type
        dynamic = self.action_goal.dynamic
        direction = self.action_goal.direction
        value = self.action_goal.value
        duration = self.action_goal.duration

        # Tell the GS to execute basic move role with parsed information
        output = heritage.basic_move(move_type,dynamic,direction,value)

        self.action_result.output = output

        return 'completed'