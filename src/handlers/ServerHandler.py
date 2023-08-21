"""
ServerHandler: App server

Hyungwon Yang
23.08.07
"""

import os, sys, io
import zipfile
import shutil
import copy
import logging
import json
import tornado.web
import tornado.websocket

from src.handlers.AlignHandler import AlignHandler
from src.handlers.DataHandler import FAhistory, DataInfo
from src.utils.DateUtils import DateUtils

CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
sendData = dict(
    message=None,
    history=None,
    success=True,
    error=None
)

fahistory = FAhistory()
dataInfo = DataInfo()

class MainHanlder(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/main.html")
        
    def post(self):
        pass
    
class progressWebSocketHandler(tornado.websocket.WebSocketHandler):
    connections = set()

    def open(self):
        self.connections.add(self)

    def on_close(self):
        self.connections.remove(self)

    @classmethod
    def send_progress(cls, progress_data):
        for connection in cls.connections:
            connection.write_message(progress_data)
            
class resultHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/result.html")
        
    def post(self):
        try:
            curSendData = copy.deepcopy(sendData)
            # extract information.
            data = json.loads(self.request.body)
            print("received: {}".format(data))
            cmd = data.get("command", None)
            dateInfo = data.get("date", None)
            langInfo = data.get("language", None)
            # read history
            fahistory.read_history()
            # follow the command.
            if cmd == "remove":
                if dateInfo is None or langInfo is None:
                    raise ValueError("Neither date: {} nor lang: {} is provided.".format(dateInfo, langInfo))
                # remove a data.
                data_name = "{}-{}".format(DateUtils.dateFormat2Raw(dateInfo), langInfo)
                folder_path = os.path.join(dataInfo.DATA_PATH, data_name)
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                # then remove history.
                fahistory.remove_history(dateInfo)
            elif cmd == "download":
                if dateInfo is None or langInfo is None:
                    raise ValueError("Neither date: {} nor lang: {} is provided.".format(dateInfo, langInfo))
                data_name = "{}-{}".format(DateUtils.dateFormat2Raw(dateInfo), langInfo)
                folder_path = os.path.join(dataInfo.DATA_PATH, data_name)
                print("zip {} files...".format(folder_path))
                # Create an in-memory byte stream to store the zip archive
                zip_stream = io.BytesIO()
                with zipfile.ZipFile(zip_stream, 'w') as zipf:
                    for root, _, files in os.walk(folder_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, folder_path)  # Use relative path for the archive
                            zipf.write(file_path, arcname=arcname)

                # Set appropriate headers for downloading
                self.set_header('Content-Type', 'application/zip')
                self.set_header('Content-Disposition', 'attachment; filename="{}.zip"'.format(data_name))

                # Write the zip archive to the response
                print("sending it to a client.")
                self.write(zip_stream.getvalue())
                print("done")
                return
            else:
                # if you need to add up more commands then use this line.
                pass
            print("history log: {}".format(fahistory.historyLog))
            self.set_header("Content-Type", "application/json")
            curSendData["history"] = fahistory.historyLog
        except Exception as e:
            self.set_status(400)
            curSendData["error"] = str(e)
            curSendData["success"] = False
        finally:
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
            lang = self.get_argument('lang')
            # print("data:{}".format(file_list))
            # save downloaded files.
            dataPath = DateUtils.makeDataDir(lang=lang)
            dateInfo = os.path.basename(dataPath).split("-")[0]
            print("data path: {}".format(dataPath))
            if dataPath:
                audio_num = 0
                for k in file_list.keys():
                    if k.endswith(".wav") or k.endswith(".txt"):
                        if k.endswith(".wav"):
                            audio_num += 1
                        save_path = os.path.join(dataPath, k)
                        print("save file: {}".format(k))
                        with io.open(save_path, 'wb') as wrt:
                            wrt.write(file_list[k][0]['body'])
                    else:
                        print("Unknown tpye: {}".format(k))
            # save it to history.
            fahistory.update_history(update_info=dict(
                                        date=DateUtils.dateRaw2Format(dateInfo),
                                        language=lang,
                                        totalAudio=str(audio_num),
                                        progress="0%"
                                    ))
            curSendData["message"] = "Upload successful"
            self.set_status(200)
            print("successful!")
        except Exception as e:
            self.set_status(400)
            curSendData["error"] = str(e)
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
            (r'/progress', progressWebSocketHandler),
            (r'/html/(.*)', tornado.web.StaticFileHandler, {"path": os.path.join(CURRENT_PATH, "../web/html/")}),
            (r'/css/(.*)', tornado.web.StaticFileHandler, {"path": os.path.join(CURRENT_PATH, "../web/css/")}),
            (r'/js/(.*)', tornado.web.StaticFileHandler, {"path": os.path.join(CURRENT_PATH, "../web/js/")}),
        ]
        tornado.web.Application.__init__(self, handlers)
    