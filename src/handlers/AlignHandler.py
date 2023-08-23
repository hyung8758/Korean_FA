"""
ALignHandler: control FA task.

Hyungwon Yang
23.08.07
"""

import os
import logging
import subprocess
import threading
import asyncio

from typing import Union, List
from src.utils.DateUtils import DateUtils
from src.handlers.DataHandler import FAhistory, DataInfo
from src.handlers.ServerHandler import progressWebSocketHandler

async def send_progress(message):
    progressWebSocketHandler.send_message(message)

class AlignHandler:
    
    def __init__(self):
        self.currentJob = None
        self.workingState = [False]
        self.faHistory = FAhistory()
        self.dataInfo = DataInfo()
        
    def getServerPort(self, server_port: Union[str, int]):
        self.server_port = server_port
    
    @staticmethod
    def run_fa(bash_cmd: str,
               currentJob: dict,
               faHistory: FAhistory,
               workingState: List[bool]):
        # Create an event loop for the thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # run the job.
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
            
            if output:
                line_output = output.strip()
                # loop.run_until_complete(send_progress(line_output))
                if line_output.startswith("The number of audio files"):
                    audio_num = int(line_output.split(":")[-1])
                    print("audio num: {}".format(audio_num))
                if line_output.endswith("successfully aligned."):
                    success_num += 1
                    print(line_output)
                    currentJob["progress"] = "{}%".format(str(int(success_num/audio_num * 100)))
                    loop.run_until_complete(send_progress(currentJob))
                    print("progress: {}".format(currentJob["progress"]))
                
            # Error log.
            if err:
                line_err = err.strip()
                print("Error:", line_err)
        
        # finish the task.
        process.wait() 
        currentJob["progress"] = "100%"
        faHistory.update_history(currentJob)
        workingState[0] = False
        loop.close()
        print("DONE FA: {}".format(currentJob))
                        
    def process(self, nj: int = 1, no_word: bool = False, no_phone: bool = False):
        # not on the process.
        # print("my working state: {}".format(self.workingState[0]))
        if self.workingState[0] is False:
            # find a task.
            self.faHistory.read_history()
            historyLog = self.faHistory.historyLog
            for each_log in historyLog:
                if each_log["progress"] == "0%":
                    try:
                        print("Start FA on {}".format(each_log['date']))
                        # do the job one by one.
                        self.currentJob = each_log
                        self.workingState[0] = True
                        data_name = "{}-{}".format(DateUtils.dateFormat2Raw(each_log["date"]), each_log["language"])
                        # prepare input arguments
                        dataPath = os.path.join(self.dataInfo.DATA_PATH, data_name)
                        options = "-nj {}".format(nj, no_word, no_phone)
                        if no_word:
                            options += " -nw "
                        if no_phone:
                            options += " -np "
                        bash_cmd = "bash forced_align.sh {} {}".format(options, dataPath)
                        print("bash command : {}".format(bash_cmd))
                        subprocess_thread = threading.Thread(target=AlignHandler.run_fa, args=(bash_cmd, 
                                                                                               self.currentJob, 
                                                                                               self.faHistory,
                                                                                               self.workingState))
                        subprocess_thread.start()
                        # process = subprocess.Popen(bash_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        # # log handling.
                        # audio_num = 0
                        # success_num = 0
                        # while True:
                        #     output = process.stdout.readline()
                        #     err = process.stderr.readline()
                        #     # 로그 종료 및 모든 프로세스가 끝났을 경우. 
                        #     if output == '' and process.poll() is not None:
                        #         break
                            
                        #     if output:
                        #         line_output = output.strip()
                        #         progressWebSocketHandler.send_message(line_output)
                        #         if line_output.startswith("The number of audio files"):
                        #             audio_num = int(line_output.split(":")[-1])
                        #             print("audio num: {}".format(audio_num))
                        #         if line_output.endswith("successfully aligned."):
                        #             success_num += 1
                        #             print(line_output)
                        #             progress_val = int(success_num/audio_num * 100)
                        #             print("progress: {}".format(progress_val))
                                
                        #     # Error log.
                        #     if err:
                        #         line_err = err.strip()
                        #         progressWebSocketHandler.send_message(line_err)
                        #         print("Error:", line_err)
                        
                        # # finish the task.
                        # # process.wait() 
                        # self.currentJob["progress"] = "100%"
                        # self.faHistory.update_history(self.currentJob)
                        # self.workingState = False
                        # print("DONE FA: {}".format(self.currentJob))
                    except Exception as e:
                        print(e)
                    finally:
                        break 
                
        # on the process.
        else:
            # wait until the job is finished.
            pass