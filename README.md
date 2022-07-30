# prometheus-data-generator

For the purposes of generating live test data, randomly generated and ported to Prometheus in real-time, we used https://github.com/little-angry-clouds/prometheus-data-generator by little-angry-clouds. The program has makefile commands configured to test, build, and push an online Docker image that can be pulled by Docker Compose. This repository was cloned and the code modified to generate data for specific metrics as defined in a new config.yml format, and to be pushed to a new Docker image. The result is a program that keeps much of the original author’s formatting and design but only uses the gauge metric format. The code, written in Python, generates random data based on sequences in the config file, which act as individual metrics, and their set parameters as outlined below.

In addition, an entirely new file, backfill.py, was coded and added to this program that generates random data as set in new config.yml parameters. This data is generated in bulk in OpenMetrics format and added to a text file that is ready for ingestion by Prometheus.

## Setup and launch
- Install Docker Desktop from https://www.docker.com/products/docker-desktop/
- Install Git from https://git-scm.com/downloads if you don’t have it already.
- From home user folder in command line:
> git clone https://github.com/joshfireforever/FSMD
- Make sure Docker Engine is running.
- From the FSMD folder in command-line run:
> docker-compose up

- Whenever stopping this project, it’s recommended that you control+C multiple times in the command-line window that you initiated docker-compose from, to force all threads to stop, if Live mode is set to True in the config file. This is because the data generator threads sleep on an interval while waiting for the next simulated forecast. If you get stuck with getting the docker project to stop because of these threads, see https://typeofnan.dev/how-to-stop-all-docker-containers.

## Backfill data generation 
The prometheus-data-generator container and program creates backfilled data at runtime automatically.
- If you wanted to recreate the backfill.txt file, such as after changing config.yml, then run this command:
docker exec -it prometheus-data-generator bash -c "python /home/appuser/prometheus_data_generator/backfill.py"
In either case, if you want to use this backfilled data, follow the steps below to import the filled data into prometheus:

### macOS
Copy and paste this whole block to run all commands in command-line in a different window than the one you ran docker-compose from:

> docker cp prometheus-data-generator:/home/appuser/backfill.txt ~/FSMD/backfill.txt && docker cp ~/FSMD/backfill.txt prometheus:/prometheus/backfill.txt && docker exec -it prometheus promtool tsdb create-blocks-from openmetrics /prometheus/backfill.txt && docker restart prometheus

Alternatively, run these commands one at a time:

- Copy the data file to local:
> docker cp prometheus-data-generator:/home/appuser/backfill.txt ~/FSMD/backfill.txt
- Copy to the prometheus container:
> docker cp ~/FSMD/backfill.txt prometheus:/prometheus/backfill.txt
- Insert into prometheus as a TSDB:
> docker exec -it prometheus promtool tsdb create-blocks-from openmetrics /prometheus/backfill.txt
- Restart prometheus to get the data to cycle:
> docker restart prometheus

### Windows
Run these commands one at a time in command-line in a different window than the one you ran docker-compose from:

- Copy the data file to local:
> docker cp prometheus-data-generator:/home/appuser/backfill.txt backfill.txt
- Copy to the prometheus container:
> docker cp backfill.txt prometheus:/prometheus/backfill.txt
- Insert into prometheus as a TSDB:
> docker exec -it prometheus promtool tsdb create-blocks-from openmetrics /prometheus/backfill.txt
- Restart prometheus to get the data to cycle:
> docker restart prometheus

- You should now be able to see backfilled metric data and newly generated live data if you search for them by name at http://localhost:9090/targets?search= - for example total_runtime_minutes, execute query, and then click Graph.

## Grafana
- An initial provisioned Grafana dashboard should already be loaded in at http://localhost:3000/dashboards. You should be able to immediately see backfill data from prometheus coming in over the intervals set in config.yml, as well as new live data coming in from prometheus-data-generator.
- If you make a change to this, the change won’t be saveable to this provisioned dashboard as Grafana forces it to be read-only. However, you can save a copy. If you wish, you can export this and replace FSMD.json in the FSMD root folder, which is where the initial dashboard is provisioned from if you recreate the Grafana container through docker compose.

## Tweaking the metrics

- FSMD/config.yml is a duplicate of what is present by default in the prometheus-data-generator image. This controls the generation of both backfilled and live metrics.
- In config.yml, each “- name:” field denotes a metric with description and metric type. The metric type is always set to gauge because of the weird way the source code was designed.
- There can be multiple sequences for each metric that will generate data with multiple parameters. However, for right now we just have a single sequence per metric for simplicity.
- eval_time -  is how long each sequence runs, which we have set to once second for now as we intend for a single value for each forecast.
- interval - number of seconds between each live data generation (a.k.a. a new forecast).
- By default this is set to 5 seconds to prevent the threads from sleeping forever, and allow for easier testing in Grafana and stopping of the containers/project in Docker. This causes new live metrics to be generated every 5 seconds, which is much less than the specified 6 hours but is much more interesting for testing and Grafana design purposes.
- To change this value to represent the actual 6 hour interval between forecasts, change this interval value to 21600 (seconds). Or set it to whatever you like for your testing purposes. This is completely up to preference right now because this will cause the actual threads to literally sleep for 6 hours. If you get stuck with getting the docker project to stop because of these threads, see https://typeofnan.dev/how-to-stop-all-docker-containers
- error_rate - the percentage value as decimal (0.0-1.0) at which bad data (within min-max) is generated for regular metrics, or the rate of a False (0) value for Boolean metrics.
- median, standard_deviation, minimum, maximum - used in a formula to generate both backfilled and live metric data. The min and max control the range that the randomly generated values can fall in.
- A value of 0 for standard_deviation indicates a Boolean metric, resulting in only integer values in range(0,1)
- live_mode - can be set to True or False in the config file. If set to False, then after generating backfill data the program and the container will quit. You can restart the container from Docker to instantly create new backfill data, if backill_mode is enabled.

### Backfilled data frequency:
- backfill_range_hours - controls how many hours back each backfilled data metric goes.
- backfill_interval_hours - controls the amount of time between each backfilled metric.
- backfill_starting_hour - controls which hour of the day each backfilled metric initiates on.
- You can add in new metrics, but keep in mind that you will need to manually add a new panel to the Grafana dashboard for each.
- After making any changes to config.yml, to get them to apply to live data you will need to run these command lines from the FSMD folder:
> docker cp config.yml prometheus-data-generator:/home/appuser
> docker restart prometheus-data-generator