"""
ServerHandler: App server

Hyungwon Yang
23.08.07
"""

import os, sys
import logging
import json
import tornado.web

from src.handlers.MainHandler import MainHandler
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))

class MainHanlder(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/main.html")
        
    def post(self):
        data = self.get_argument("data")
        MainHandler.process(data)
        self.write(f"Received POST data: {data}")
        
class resultHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/result.html")

class uploadHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("../web/html/upload.html")
    
    def post(self):
        # 파일 다운로드 관리.
        try:
            file_list = dict()
            for each_key in self.request.files.keys():
                file_list[each_key] = self.request.files[each_key]
            # print("data:{}".format(file_list))
            self.set_status(200)
            self.write(json.dumps({"message": "Upload successful", "success": True}))
            print("successful!!")
        except Exception as e:
            self.set_status(400)
            self.write(json.dumps({"error":str(e)}))
            print("failed!!")

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
    