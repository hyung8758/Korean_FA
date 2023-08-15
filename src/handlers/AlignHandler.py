"""
ALignHandler: control FA task.

Hyungwon Yang
23.08.07
"""

import os, sys
import logging
import argparse

class AlignHandler():
    
    def __init__(self):
        pass
    
    @staticmethod
    def process(json_data: dict = None):
        logging.info("start!")
        logging.info("received: {}".format(json_data))