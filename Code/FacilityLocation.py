# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""


import pandas as pd
import csv
import time
import os
import gurobipy as gp
from gurobipy import GRB
import sys


#Read files as pandas dataframe
Dserved = pd.read_csv("/home/Quand/Data/Dserved.csv", encoding='latin-1', low_memory=False)
Facility = pd.read_csv("/home/Quand/Data/Facility_geographic_information_reduced.csv",index_col='Name', encoding='latin-1')
Distance = pd.read_csv("/home/Quand/Data/TractDistance.csv", encoding='latin-1', low_memory=False)



Dserved = Dserved.set_index('GEOID')
Distance = Distance.set_index('GEOID_x')

Distance = Distance[Distance['distance'] <= 48.2803] 

#Write initial results files with headers
Results_df = pd.DataFrame(columns = ["k",'New clients', 'Run Time'])
Results_df.to_csv(path_or_buf="/home/Quand/Results/New_Clients_Results.csv",
                  sep=",",
                  mode='a',
                  index = False)

Opened_facilities_df = pd.DataFrame(columns = ["k", "Clients", "Longitude", "Latitude"])
Opened_facilities_df.to_csv(path_or_buf="/home/Quand/Results/New_Client_New_Facilities.csv",
                            sep=",",
                            mode='a',
                            index = False)


# Function to record results
def record_results(model):
    global Results_df
    Results_df = Results_df.append(pd.DataFrame({'k':k,
                                                 'New clients':[unserved_clients.x],
                                                 'Run Time':[toc-tic]}))
    
# Function to record newly opened facilities
def record_opened_facilities(model):
    global Opened_facilities_df
    tol = 0.01
    solution_z = model.getAttr('x', z)
    solution_y = model.getAttr('x', y)
    for facility in New_potential_facilities:
        if solution_z[facility] > tol: 
            Opened_facilities_df = Opened_facilities_df.append(pd.DataFrame({'k':k,
                                                                             'Clients':[solution_y.sum('*',facility).getValue()],
                                                                             'Longitude':[Dserved.at[facility,'Tract_Long']],
                                                                             'Latitude':[Dserved.at[facility,'Tract_Lat']]}))


def solve_model(this_model):
    #Solves optimization model and records values
    global tic, toc

    tic = time.perf_counter()
    
    this_model.setObjective(unserved_clients, GRB.MAXIMIZE)
    this_model.optimize()
    toc = time.perf_counter()
    
    record_opened_facilities(this_model)
    record_results(this_model)


tic = time.perf_counter()

Distance['flow'] = list(zip(Distance.index, Distance.GEOID_y))
DistanceD = dict(zip(Distance.flow, Distance.distance))

c = 1836.9879489057403

Served_Tracts = set([tract for tract in list(Dserved.index) if Dserved.at[tract,'demand_served']>=0])
Unserved_Tracts = set([tract for tract in list(Dserved.index) if Dserved.at[tract,'demand_left']>=0])
New_potential_facilities = set([item[1] for item in list(DistanceD.keys())])
    
#Define set of unserved clients
Unserved_tracts_by_new_facilities = {}
for facility in New_potential_facilities:
    Unserved_tracts_by_new_facilities[facility] = set(item[0] for item in list(DistanceD.keys()) if item[1]==facility)

#Define demand
served_demand, unserved_demand = {},{}
for tract in Served_Tracts:
    served_demand[tract] = Dserved.at[tract,'demand_served']
for tract in Unserved_Tracts:
    unserved_demand[tract] = Dserved.at[tract,'demand_left']
    

served_new_flow, served_new_dist = gp.multidict(DistanceD)

if not bool(DistanceD): #Dictionary is Empty
    unserved_new_flow, unserved_new_dist = {},{}
else:
    unserved_new_flow, unserved_new_dist = gp.multidict(DistanceD)


#Make the model
mod = gp.Model("Facility Location")
mod.setParam('OutputFlag', 0)

#Define varriables
y = mod.addVars(unserved_new_flow, vtype=GRB.CONTINUOUS, name="y")
z = mod.addVars(New_potential_facilities, vtype=GRB.BINARY, name="z")

print(y)

new_sum_dist = mod.addVar(vtype=GRB.CONTINUOUS, name="new_sum_dist") #Sum travel distance for new clients
unserved_clients = mod.addVar(vtype=GRB.CONTINUOUS, name="unserved_clients")

mod.update()


#Make constraints

# Unserved demand up to maximum demand
unserved_demand_cons = mod.addConstrs((y.sum(tract,'*') <= unserved_demand[tract] for tract in Unserved_Tracts), name="unserved_demand")

# Only use new facilities that are opened
opened_cons_new = mod.addConstrs((y[tract,facility] <= c*z[facility] for (tract,facility) in y), name="new_demand")
    
#Enforce that if a new facility is opened, all possible unmet demand in it's radius must be served
forced_demand = mod.addConstrs((y.sum(tract,'*') >= unserved_demand[tract]*z[facility] 
                                for facility in New_potential_facilities 
                                for tract in Unserved_tracts_by_new_facilities[facility]), name="forced_demand")

# Restrict number of opened facilities (0 for initialization)
k_cons = mod.addConstr(z.sum('*') <= 0, name="k_cons")


# Unserved clients
unserved_client_const = mod.addConstr(y.sum() == unserved_clients)


#Objective function
mod.setObjective(0, GRB.MAXIMIZE)


toc = time.perf_counter()
print(f"Setting up optimization model for Ohio took {toc - tic:0.4f} seconds", flush=True)
sys.stdout.flush()


## for a range of k values
for k in range(1,50): 
    Opened_facilities_df = pd.DataFrame(columns = ["k", "Clients","Longitude", "Latitude"])
    Results_df = pd.DataFrame(columns = ["k", 'New clients', 'Run Time'])
    mod.remove(k_cons)
    k_cons = mod.addConstr(z.sum('*') <= k, name="k_cons")
    mod.update()
    solve_model(mod)
        
    print(f"Completed model for Ohio with k = {k} in {toc-tic:0.4f} seconds", flush=True)

    Opened_facilities_df.to_csv(path_or_buf="/home/Quand/Results/New_Client_New_Facilities.csv",
                                    sep=",",
                                    mode='a',
                                    header=False,
                                    index = False)


    Results_df.to_csv(path_or_buf="/home/Quand/Results/New_Clients_Results.csv",
                                    sep=",",
                                    mode='a',
                                    header=False,
                                    index = False)
    