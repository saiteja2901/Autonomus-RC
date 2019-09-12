import sys
from environment import *
import time
import random
import pygame
import csv
import os
import torch
from tools import DDPG_Actor
from tools import getHeading, bool2num

np.random.seed(1234)
device = 'cuda' if torch.cuda.is_available() else 'cpu'

if __name__ == "__main__":

	pygame.init()
	pygame.font.init()
	env = environment(traj_num=6,model='ddpg')

	
	action_dim = 2 # steer, throttle
	state = env.getState()
	state_dim = len(state)
	print('action_dimension:', action_dim, ' --- state_dimension:', state_dim)
	
	# Initializing the Agent for DDPG and load the trained weights
	actor = DDPG_Actor(state_dim=state_dim, action_dim = action_dim).to(device)
	actor.load_state_dict(torch.load( '../weights/ddpg/actor_net_720.pth'))

	destinationFlag = False
	collisionFlag = False
	awayFlag = False
	carla_startFlag = False	

	# define the test tire frictions and vehicle mass
	setups = [(3.0,1700.0),(3.5,1800.0),(4.0,1900.0)]
	# define the headers of the csv file to be saved
	headers = ['time','world_x','world_y','world_heading','local_vx','local_vy','total_v','slip_angle',
	'cte','cae','traj_index','reward','steer','throttle','collisionFlag','desitinationFlag','awayFlag']

	
	os.makedirs('./test/ddpg/',exist_ok=True)
	for setup in setups:
		print('TESTING --- setup: ', setup)
		save_path = './test/ddpg/'+ str(setup[0])+'_'+str(setup[1])
		save_file = open(save_path + '.csv','w')
		writer = csv.writer(save_file)
		writer.writerow(headers)

		env.reset(traj_num=6, testFlag=True, test_friction=setup[0], test_mass=setup[1])

		t0 = time.time()
		first_step_pass = False

		while(True):
			env.render()

			# make sure the connection with carla is ok
			tmp_control = env.world.player.get_control()
			if tmp_control.throttle == 0 and carla_startFlag==False:
				tmp_control = carla.VehicleControl(
								throttle = 0.5,
								steer = 0,
								brake = 0.0,
								hand_brake = False,
								reverse = False,
								manual_gear_shift = False,
								gear = 0)
				env.world.player.apply_control(tmp_control)
				continue
			carla_startFlag = True

			if time.time()-t0 < 0.5:
				# make sure the collision sensor is empty
				env.world.collision_sensor.history = []

			if time.time()-t0 > 0.5:

				if not first_step_pass:
					steer = 0.0
					throttle = 0.0
					hand_brake = False
				else:
					action = actor.test(tState)
					action = np.reshape(action, [1,2])

					steer = action[0,0]
					throttle = action[0,1]	

				next_state, reward, collisionFlag, destinationFlag, awayFlag, control = env.step(steer=steer, throttle=throttle)
				next_state = np.reshape(next_state, [1, state_dim])
				
				tState = next_state

				# prepare the state information to be saved
				t = time.time() - t0
				location = env.world.player.get_location()
				wx = location.x
				wy = location.y
				course = getHeading(env)
				vx = env.velocity_local[0]
				vy = env.velocity_local[1]
				speed = np.sqrt(vx*vx + vy*vy)
				slip_angle = env.velocity_local[2]
				cte = tState[0,2]
				cae = tState[0,4]
				traj_index = env.traj_index
				steer = control.steer
				throttle = control.throttle
				cf = bool2num(collisionFlag)
				df = bool2num(destinationFlag)
				af = bool2num(awayFlag)
				
				# save to the csv file for further analysis
				print('time stamp: ', t)
				writer.writerow([t,wx,wy,course,vx,vy,speed,slip_angle,cte,cae,traj_index,reward,steer,throttle,cf,df,af])
				
				endFlag = collisionFlag or destinationFlag or awayFlag

				if endFlag:
					break
				
				first_step_pass = True 
		