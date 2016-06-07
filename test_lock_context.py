from __future__ import print_function
from lib.common import lock_context, init_logging
import time
import logging

init_logging()

with lock_context("gdc_mirror_root", "mirror"):
    logging.info("Doing work..")
    time.sleep(5)