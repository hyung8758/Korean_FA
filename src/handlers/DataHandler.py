"""
DataHandler: data class.

Hyungwon Yang
23.08.15
"""
import os
import json
import logging
import shutil
import datetime
import argparse

CURRENT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")

class FAhistory:
    """
    while processing a FA task, all the log information will be saved here.
    mySQL might be the better way to hanlde this kind of information,
    but this tool will not use it because it is not only running on a docker but 
    various OS systems. 
    Since the OS system is not fixed, using mysql will unstablize this tool. 
    """
    def __init__(self, history_path: str = "log/history"):
        # get history info
        self.history_file = "history.json"
        self.HISTORY_PATH = os.path.join(CURRENT_PATH, history_path)
        self.history_file_path = os.path.join(self.HISTORY_PATH, self.history_file)
        # check history data.
        if not os.path.exists(self.HISTORY_PATH):
            # make history path.
            os.makedirs(self.HISTORY_PATH)
        if not os.path.exists(self.history_file_path):
            # make emty history file.
            with open(self.history_file_path, 'w', encoding='utf-8'):
                pass
        
    def read_history(self):
        with open(self.history_file_path, 'r', encoding='utf-8') as txt:
            self.historyLog = json.load(txt)
        return self.historyLog
    
    def save_history(self):
        json_file = json.dumps(self.historyLog, indent=4)
        with open(self.history_file_path, 'w', encoding='utf-8') as wrt:
            wrt.write(json_file)
