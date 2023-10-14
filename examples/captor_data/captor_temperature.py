#!/usr/bin/env python3

#-------------------------------------------------------------------#
# Copyright (C) 2019-2023 by Serguei Tarassov <serge@arbinada.com>  #
# Distributed freely under the MIT License                          #
#-------------------------------------------------------------------#

"""
JSON SAX parser examples
Captor temperature stream

Input stream example:

[
    {
        "timestamp": "2023-01-02 01:02:34",
        "captor_id": "42326a90-6aae-11ee-a361-4339b9d98b6a",
        "temperature": 36.6
    },
    ...
]
"""

import io
import sys
import os
sys.path.append(os.path.realpath(os.path.join(os.path.dirname(__file__), "../..")))
from json_sax import SAXParser, SAXHandlerIntf, LiteralTokenKind, NumericTokenKind, TextPos

class CaptorDataHandler(SAXHandlerIntf):
    def __init__(self) -> None:
        self._level = 0
        self._sum = 0.0
        self._member = None
        self._data = {}
        self._pos = TextPos()
        super().__init__()

    def on_literal(self, _kind: LiteralTokenKind, text: str):
        print(f"Skip unexpected literal '{text}' at position {str(self._pos)}")

    def on_number(self, kind: NumericTokenKind, text: str):
        if kind != NumericTokenKind.NT_UNKNOWN:
            self._data[self._member] = float(text)
        else:
            print(f"Skip unexpected numeric value '{text}' at position {str(self._pos)}")

    def on_string(self, text: str):
        self._data[self._member] = text

    def on_begin_object(self):
        self._data = {}

    def on_member_name(self, text: str):
        self._member = text

    def on_end_object(self, _member_count: int):
        self._sum += self._data.get("temperature", 0)
        print(".", end = "")

    def on_begin_array(self):
        if self._level > 0:
            raise Exception("Invalid stream format")
        print("Start processing")
        self._level += 1

    def on_end_array(self, element_count: int):
        print("\nProcessing finished")
        print(f"Timeseries length: {element_count}")
        avg_temp = self._sum / element_count
        print(f"Average temperature is: {avg_temp}")

    def textpos_changed(self, pos: TextPos):
        self._pos = pos

def run():
    handler = CaptorDataHandler()
    data_filename = os.path.realpath(os.path.join(os.path.dirname(__file__), "captor_data.json"))
    with io.open(data_filename) as source:
        parser = SAXParser(source, handler)
        parser.run()

if __name__ == "__main__":
    run()
