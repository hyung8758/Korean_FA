"""
ALignHandler: control FA task.

Hyungwon Yang
23.08.07
"""

import os, sys
import yaml
import argparse
import logging
import websocket
import subprocess

from typing import Union
from src.utils.DateUtils import DateUtils
from src.handlers.DataHandler import FAhistory, DataInfo

class AlignHandler:
    
    def __init__(self):
        self.currentJob = None
        self.workingState = False
        self.faHistory = FAhistory()
        self.dataInfo = DataInfo()
        
    def connectWebsocket(self, server_port: Union[str, int]):
        # websocket
        self.ws = websocket.create_connection("ws://localhost:{}/progress".format(server_port))
    
    def process(self, nj: int = 1, no_word: bool = False, no_phone: bool = False):
        # not on the process.
        if self.workingState is False:
            # find a task.
            self.faHistory.read_history()
            historyLog = self.faHistory.historyLog
            for each_log in historyLog:
                if each_log["progress"] == "0%":
                    # do the job one by one.
                    self.currentJob = each_log
                    self.workingState = True
                    data_name = "{}-{}".format(DateUtils.dateFormat2Raw(each_log["date"]), each_log["language"])
                    # prepare input arguments
                    dataPath = os.path.join(self.dataInfo.DATA_PATH, data_name)
                    options = "-nj {} -nw {} -np {}".format(nj, no_word, no_phone)
                    bash_cmd = "bash forced_align.sh {} {}".format(options, dataPath)
                    process = subprocess.Popen(bash_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    # log handling.
                    audio_num = 0
                    success_num = 0
                    while True:
                        output = process.stdout.readline()
                        err = process.stderr.readline()
                        # 로그 종료 및 모든 프로세스가 끝났을 경우. 
                        if output == '' and process.poll() is not None:
                            break
                        # Normal log.
                        if output:
                            line_output = output.strip()
                            if line_output.startswith("The number of audio files"):
                                audio_num = int(line_output.split(":")[-1])
                                print("audio num: {}".format(audio_num))
                            if line_output.endswith("successfully aligned."):
                                success_num += 1
                                print(line_output)
                                progress_val = int(success_num/audio_num * 100)
                                print("progress: {}".format(progress_val))
                            
                        # Error log.
                        if err:
                            line_err = err.strip()
                            print("Error:", line_err)
                    
                    # finish the task.
                    self.currentJob["progress"] = "100%"
                    self.faHistory.update_history(self.currentJob)
                    self.workingState = False
                    print("DONE FA: {}".format(self.currentJob))
            
        # on the process.
        else:
            # wait until the job is finished.
            pass