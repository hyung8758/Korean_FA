"""
LogUtils: log.

Hyungwon Yang
23.08.27
"""
import os
import logging

CURRENT_PATH = "/".join([os.path.dirname(os.path.abspath(__file__)), "../.."])
def initLog(log_path: str, log_in_date: str, log_file_name: str, log_format: str):

    # make log dir. (in date dir?)
    logDir = os.path.join(CURRENT_PATH, log_path)
    if not os.path.exists(logDir):
        os.makedirs(logDir)
    # make date dir if necessary.
    makeLogDateDir = log_in_date
    if makeLogDateDir:
        # get current date
        from datetime import date
        curDate = date.today().strftime("%y%m%d")
        curDateDir = os.path.join(logDir, curDate)
        if not os.path.exists(curDateDir):
            os.makedirs(curDateDir)
        logDir = curDateDir
    
    # set config info.
    logFilePath = os.path.join(logDir, log_file_name)
    logging.basicConfig(level=logging.INFO, format=log_format, filename=logFilePath)
    logging.info("log save path: {}".format(logFilePath))
    logging.info("START logging...")