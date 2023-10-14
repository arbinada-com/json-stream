#!/usr/bin/env python3

#-------------------------------------------------------------------#
# Copyright (C) 2019-2023 by Serguei Tarassov <serge@arbinada.com>  #
# Distributed freely under the MIT License                          #
#-------------------------------------------------------------------#

"""
Profiling of JSON stream (SAX) parser

Dependencies:
    $ pip install snakeviz
Run profiler:
    $ python3 -m cProfile -o /tmp/tmp.prof json_sax_profile.py <test_data_file.json>
View profiling results:
    $ snakeviz /tmp/tmp.prof
"""

import io
import sys
import os

sys.path.append(os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))
from json_sax import SAXParser, SAXHandlerBasic

def run_profile(dataset_filename: str):
    print("Profiling started")
    print(f"Test data: {dataset_filename}")
    filepath = os.path.realpath(os.path.join(os.path.dirname(__file__), "data", dataset_filename))
    with io.open(filepath, "r", encoding = "utf-8") as reader:
        handler = SAXHandlerBasic()
        parser = SAXParser(reader, handler)
        parser.run()
    print("Profiling finished")

if __name__ == "__main__":
    dataset_filename = "dataset_medium.json"
    if len(sys.argv) > 1:
        dataset_filename = sys.argv[1]
    run_profile(dataset_filename)
