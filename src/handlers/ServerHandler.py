"""
ServerHandler: App server

Hyungwon Yang
23.08.07
"""

import os, sys, io
import shutil
import copy
import logging
import json
import tornado.web

from src.handlers.AlignHandler import AlignHandler
from src.handlers.DataHandler import FAhistory
from src.utils.DateUtils import DateUtils

CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
sendData = dict(
    message=None,
    history=None,
    success=True,
)
class MainHanlder(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/main.html")
        
    def post(self):
        pass
        
class resultHandler(tornado.web.RequestHandler):
    fahistory = FAhistory()
    def get(self):
        self.render("../web/html/result.html")
        
    def post(self):
        curSendData = copy.deepcopy(sendData)
        # extract information.
        data = json.loads(self.request.body)
        print("received: {}".format(data))
        cmd = data.get("command", None)
        # read history
        historyLog = self.fahistory.read_history()
        # follow the command.
        if cmd == "remove":
            pass
        elif cmd == "download":
            pass
        else:
            pass
        print("history log: {}".format(historyLog))
        self.set_header("Content-Type", "application/json")
        curSendData["history"] = historyLog
        self.write(json.dumps(curSendData))

class uploadHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/upload.html")
    
    def post(self):
        # 파일 다운로드 관리.
        try:
            curSendData = copy.deepcopy(sendData)
            file_list = dict()
            print("file number: {}".format(self.request.files.keys()))
            for each_key in self.request.files.keys():
                file_list[each_key] = self.request.files[each_key]
            # print("data:{}".format(file_list))
            # save downloaded files.
            dataPath = DateUtils.makeDataDir(lang=self.get_argument('lang'))
            print("data path: {}".format(dataPath))
            if dataPath:
                for k in file_list.keys():
                    if k.endswith(".wav") or k.endswith(".txt"):
                        save_path = os.path.join(dataPath, k)
                        print("save file: {}".format(k))
                        with io.open(save_path, 'wb') as wrt:
                            wrt.write(file_list[k][0]['body'])
                    else:
                        logging.info("Unknown tpye: {}".format(k))
            # save it to history.
            curSendData["message"] = "Upload successful"
            self.set_status(200)
            print("successful!")
        except Exception as e:
            self.set_status(400)
            curSendData["error"] = e
            curSendData["success"] = False
            print("failed!: {}".format(e))
            # remove previous generated data dir.
            if os.path.exists(dataPath):
                shutil.rmtree(dataPath)
        finally:
            self.write(json.dumps(curSendData))

class App(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/', MainHanlder),
            (r'/result', resultHandler),
            (r'/upload', uploadHandler),
            (r'/html/(.*)', tornado.web.StaticFileHandler, {"path": os.path.join(CURRENT_PATH, "../web/html/")}),
            (r'/css/(.*)', tornado.web.StaticFileHandler, {"path": os.path.join(CURRENT_PATH, "../web/css/")}),
            (r'/js/(.*)', tornado.web.StaticFileHandler, {"path": os.path.join(CURRENT_PATH, "../web/js/")}),
        ]
        tornado.web.Application.__init__(self, handlers)
    