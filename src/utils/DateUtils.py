"""
DateUtils: control date and relative dirs and files.

Hyungwon Yang
23.08.15
"""
import os
import shutil
import datetime
from typing import Union

class DateUtils:
    
    def __init__(self):
        raise("This class cannot be initialized.")
    
    @staticmethod
    def getCurrentDate(format: bool=False) -> str:
        now = datetime.datetime.now()
        year = '{:02d}'.format(now.year)
        month = '{:02d}'.format(now.month)
        day = '{:02d}'.format(now.day)
        hour = '{:02d}'.format(now.hour)
        minute = '{:02d}'.format(now.minute)
        second = '{:02d}'.format(now.second)
        output =  "{}{}{}{}{}{}".format(year, month, day, hour, minute, second)
        if format:
            return DateUtils.dateRaw2Format(output)
        else:
            return output

    @staticmethod
    def dateRaw2Format(rawDate: str) -> str:
        dl = ",".join(rawDate[i:i + 2] for i in range(0, len(rawDate), 2)).split(",")
        return "{}/{}/{} {}:{}:{}",format(dl[0],dl[1],dl[2],dl[3],dl[4],dl[5])

    @staticmethod
    def dateFormat2Raw(formatDate: str) -> str:
        return formatDate.replace(":","").replace("/","").replace(" ","")
        
    @staticmethod
    def makeDataDir(lang: str, curTime: str = None, dataDir: str = 'data', dateFormat: bool=False) -> Union[str,None]:
        try:
            if curTime is None:
                curTime = DateUtils.getCurrentDate(format=dateFormat)
            dir_name = "{}-{}".format(curTime, lang)
            data_file_path = os.path.join(dataDir, dir_name)
            if os.path.exists(data_file_path):
                # it should not exist... but if it is there? remove it first.
                shutil.rmtree(data_file_path)
            os.makedirs(data_file_path)
            return data_file_path
        except Exception as e:
            print(e)
            return None