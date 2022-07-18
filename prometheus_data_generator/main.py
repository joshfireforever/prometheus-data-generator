#!/usr/bin/env python3

#I cloned this from https://github.com/little-angry-clouds/prometheus-data-generator

import time
import random
import threading
import logging
import backfill
from os import _exit, environ
import yaml
import scipy.stats as stats
from flask import Flask, Response
from prometheus_client import Gauge, Counter, Summary, Histogram
from prometheus_client import generate_latest, CollectorRegistry
import datetime
from datetime import datetime

live_mode = True
times_of_day = []

if "PDG_LOG_LEVEL" in environ:
    supported_log_levels = ["INFO", "ERROR", "DEBUG"]
    if environ["PDG_LOG_LEVEL"].upper() not in supported_log_levels:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger = logging.getLogger("prometheus-data-generator")
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("prometheus-data-generator")
    logger.setLevel(environ["PDG_LOG_LEVEL"].upper())
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("prometheus-data-generator")


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


class PrometheusDataGenerator:
    def __init__(self):
        """
        Initialize the flask endpoint and launch the function that will throw
        the threads that will update the metrics.
        """
        self.app = Flask(__name__)
        self.serve_metrics()
        self.init_metrics()

    def init_metrics(self):
        """
        Launch the threads that will update the metrics.
        """
        self.threads = []
        self.registry = CollectorRegistry()
        self.data = read_configuration()

        live_mode = self.data["live_mode"]

        if live_mode:
            logger.info("LIVE MODE IS ENABLED")
        else:
            logger.info("LIVE MODE IS DISABLED, EXITING.")
            quit()


        for metric in self.data["config"]:
            if "labels" in metric:
                labels = metric["labels"]
            else:
                labels = []
            if metric["type"].lower() == "counter":
                instrument = Counter(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            elif metric["type"].lower() == "gauge":
                instrument = Gauge(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            elif metric["type"].lower() == "summary":
                instrument = Summary(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            elif metric["type"].lower() == "histogram":
                # TODO add support to overwrite buckets
                instrument = Histogram(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            else:
                logger.warning(
                    "Unknown metric type {type} for metric {name}, ignoring.".format(**metric)
                )

            t = threading.Thread(
                target=self.update_metrics,
                args=(instrument, metric),
            )
            t.start()
            self.threads.append(t)

    def update_metrics(self, metric_object, metric_metadata):
        """
        Updates the metrics.

        Arguments:
        metric_object: a Prometheus initialized object. It can be a Gauge,
          Counter, Histogram or Summary. For this program we only us Gauge as 
          this is the only type that allows for direct setting.
        metric_metadata: the configuration related to the initialzed Prometheus
          object. It comes from the config.yml.
        """
        self.stopped = False
        while True:
            if self.stopped:
                break

            for sequence in metric_metadata["sequence"]:
                if self.stopped:
                    break

                if "labels" in sequence:
                    labels = [key for key in sequence["labels"].values()]
                else:
                    labels = []

                if "eval_time" in sequence:
                    timeout = time.time() + sequence["eval_time"]
                else:
                    logger.warning(
                        "eval_time for metric {} not set, setting default to 1.".format(metric_metadata["name"])
                    )
                    timeout = time.time() + 1


                logger.debug(
                    "Changing sequence in {} metric".format(metric_metadata["name"])
                )

                if "interval" in sequence:
                    interval = sequence["interval"]
                else:
                    logger.warning(
                        "interval for metric {} not set, setting default to 1.".format(metric_metadata["name"])
                    )
                    interval = 1

                while True:
                    if self.stopped:
                        break

                    if time.time() > timeout:
                        break

                    stddev = sequence["standard_deviation"]
                    bad_data_rate = sequence["bad_data_rate"]
                    missing_data_rate = sequence["missing_data_rate"]

                    #Generate valid value within specs
                    med = sequence["median"]
                    mmin = sequence["minimum"]
                    mmax = sequence["maximum"]
                    dist = stats.truncnorm((mmin - med) / stddev, (mmax - med) / stddev, loc=med, scale=stddev)
                    value = dist.rvs(1)[0]
                    #insert bad data
                    bad_instances = int(bad_data_rate*100)
                    valid_instances = 100 - bad_instances
                    bad_data_bool = valid_instances * [False] + bad_instances * [True]
                    random.shuffle(bad_data_bool)
                    if (bad_data_bool[0]):
                        value = random.uniform(mmin, mmax)
                    #insert missing data
                    missing_instances = int(missing_data_rate*100)
                    valid_instances = 100 - missing_instances
                    missing_data_bool = valid_instances * [False] + missing_instances * [True]
                    random.shuffle(missing_data_bool)
                    if (missing_data_bool[0]):
                        value = -1 #-1 value is our representation of missing data
                    
                    metric_object.set(value)

                    time.sleep(interval)

    def serve_metrics(self):
        """
        Main method to serve the metrics. It's used mainly to get the self
        parameter and pass it to the next function.
        """
        @self.app.route("/")
        def root():
            """
            Exposes a blank html page with a link to the metrics.
            """
            page = "<a href=\"/metrics/\">Metrics</a>"
            return page

        @self.app.route("/metrics/")
        def metrics():
            """
            Plain method to expose the prometheus metrics. Every time it's
            called it will recollect the metrics and generate the rendering.
            """
            metrics = generate_latest(self.registry)
            
            return Response(metrics,
                            mimetype="text/plain",
                            content_type="text/plain; charset=utf-8")

        @self.app.route("/-/reload")
        def reload():
            """
            Stops the threads and restarts them.
            """
            self.stopped = True
            for thread in self.threads:
                thread.join()
            self.init_metrics()
            logger.info("Configuration reloaded. Metrics will be restarted.")
            return Response("OK")

    def run_webserver(self):
        """
        Launch the flask webserver on a thread.
        """
        threading.Thread(
            target=self.app.run,
            kwargs={"port": "9000", "host": "0.0.0.0"}
        ).start()


if __name__ == "__main__":
    PROM = PrometheusDataGenerator()
    PROM.run_webserver()
