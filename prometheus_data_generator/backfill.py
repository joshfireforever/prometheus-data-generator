import os
from os import _exit, environ
import random
import yaml
import scipy.stats as stats
from datetime import datetime
from datetime import timedelta
import time

def read_configuration():
    """
    Read configuration from the environmental variable PDG_PATH.
    """
    # TODO validate the yaml
    if "PDG_CONFIG" in environ:
        path = environ["PDG_CONFIG"]
    else:
        path = "config.yml"
    config = yaml.safe_load(open(path))
    return config
    
def get_times(data):
	range_hours = data["backfill_range_hours"]
	interval_hours = data["backfill_interval_hours"]
	starting_hour = data["backfill_starting_hour"]

	current_hour = starting_hour
	times_of_day = []

	while current_hour < 24:
		times_of_day.append(current_hour)
		current_hour = current_hour + interval_hours

	now = datetime.now()
	now_hours = datetime(now.year,now.month,now.day,now.hour)

	starting_time = now_hours - timedelta(hours=range_hours)

	current_time = starting_time
	times = []
	times_epoch = []

	while current_time < now:
		if (current_time.hour in times_of_day):
			times.append(current_time)
			current_time = current_time + timedelta(hours=interval_hours)
		else:
			current_time = current_time + timedelta(hours=1)

	for time in times:
		epoch = (time - datetime(1970,1,1)).total_seconds()
		times_epoch.append(epoch)

	return times_epoch
	
backfill_file = open("backfill.txt", "w")
data = read_configuration()

for metric in data["config"]:
	met_name = metric['name']
	met_desc = metric['description']
	met_type = metric['type']
	
	backfill_file.write(f"# TYPE {met_name} {met_type}\n")
	backfill_file.write(f"# HELP {met_name} {met_desc}\n")
	for sequence in metric["sequence"]:
	
		stddev = sequence["standard_deviation"]
		bad_data_rate = sequence["bad_data_rate"]
		missing_data_rate = sequence["missing_data_rate"]

		times_epoch = get_times(sequence)
		num_instances = len(times_epoch)

		#generate random data within specs
		med = sequence["median"]
		mmin = sequence["minimum"]
		mmax = sequence["maximum"]
		dist = stats.truncnorm((mmin - med) / stddev, (mmax - med) / stddev, loc=med, scale=stddev)
		values = dist.rvs(num_instances)
		#insert bad data
		bad_instances = int(bad_data_rate*num_instances)
		valid_instances = num_instances - bad_instances
		bad_data_bool = valid_instances * [False] + bad_instances * [True]
		random.shuffle(bad_data_bool)
		for x in range(num_instances):
			if (bad_data_bool[x]):
				values[x] = random.uniform(med-(stddev*3), med+(stddev*3))
		#insert missing data
		missing_instances = int(missing_data_rate*num_instances)
		valid_instances = num_instances - missing_instances
		missing_data_bool = valid_instances * [False] + missing_instances * [True]
		random.shuffle(missing_data_bool)
		for x in range(num_instances):
			if (missing_data_bool[x]):
				values[x] = -1 #-1 value is our representation of missing data

		
		for x in range(num_instances):
			backfill_file.write(f"{met_name} {values[x]} {times_epoch[x]}\n")

backfill_file.write(f"# EOF")
backfill_file.close()

print("Backfill file created > backfill.txt.")
