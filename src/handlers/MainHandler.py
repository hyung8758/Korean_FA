"""
mainHandler: control web page.

Hyungwon Yang
23.08.07
"""

import os, sys
import logging
import argparse

class MainHandler():
    
    def __init__(self):
        pass
    
    @staticmethod
    def process(json_data: dict = None):
        logging.info("start!")
        logging.info("received: {}".format(json_data))