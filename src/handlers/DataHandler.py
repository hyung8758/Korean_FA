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
from dataclasses import dataclass

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
        # history format
        self.history_form = dict(
            date="unknown",
            language="unknown",
            totalAudio="0",
            progress="0%"
        )
        
        # get history info
        self.history_file = "history.json"
        self.HISTORY_PATH = os.path.join(CURRENT_PATH, history_path)
        self.history_file_path = os.path.join(self.HISTORY_PATH, self.history_file)
        
        # check history data.
        if not os.path.exists(self.HISTORY_PATH):
            # make history path.
            os.makedirs(self.HISTORY_PATH)
        if not os.path.exists(self.history_file_path):
            # make empty list in history file.
            with open(self.history_file_path, 'w', encoding='utf-8') as wrt:
                wrt.write("[]")
        
        # history contained variable.
        self.historyLog = []
        
    def read_history(self):
        with open(self.history_file_path, 'r', encoding='utf-8') as txt:
            self.historyLog = json.load(txt)
    
    def get_history(self):
        if not self.historyLog:
            self.read_history()
        return self.historyLog
    
    def save_history(self):
        json_file = json.dumps(self.historyLog, indent=4)
        with open(self.history_file_path, 'w', encoding='utf-8') as wrt:
            wrt.write(json_file)

    def remove_history(self, date: str):
        # if historyLog is not found, read it from a history file.
        if not self.historyLog:
            self.read_history()
        for idx, each_history in enumerate(self.historyLog):
            if date == each_history['date']:
                del self.historyLog[idx]
                self.save_history()

    def update_history(self, update_info: dict):
        # check update_info. get every requisite info?
        for k in update_info.keys():
            if k not in self.history_form.keys():
                raise ValueError("{} is not defined".format(k))
        # if historyLog is not found, read it from a history file.
        if not self.historyLog:
            self.read_history()
        check_list = [ idx for idx, each_log in enumerate(self.historyLog) if update_info["date"] == each_log["date"] ]
        # if update_info is found in historyLog, then overwrite it.
        if check_list:
            self.historyLog[check_list[0]] = update_info
        else: 
            # if update info is not found in historyLog, then add it.
            self.historyLog.append(update_info)
        # rewrite history file.
        self.save_history()
        
        
@dataclass    
class DataInfo:
    DATA_PATH = os.path.join(CURRENT_PATH, 'data')
    