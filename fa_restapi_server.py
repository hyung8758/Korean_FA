"""
Korean_FA restapi server.py: for restapi connection 

Hyungwon Yang
24.01.19
"""

import os
import json
import wave
import tempfile
import subprocess
from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop


"""
FA json guide
send to FA:
{ Content-Type: multipart/form-data
    'audio_file' : [audio_file]
    'text_file' : [text_file]
    'nj' : 1,  # number of job (multiprocessing option)
    'no_word' : false, # skip word-level FA option
    'no_phone': false, # skip phone-level FA option
    
}

FA return:
{
    'success' : true
    'log' : 'log message'
    'result':
}

"""
SEND_FORM = dict(success=True, log='', result='')
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(CURRENT_PATH, "data")

AUDIO_CHANNEL = 1
AUDIO_SAMPLEWIDTH = 2

server_port = 30010


class FAtaskHandler(RequestHandler):
    def get(self):
        pass

    def post(self):
        try:
            # data = json.loads(self.request.body)
            # print("recevied message: {}".format(data))
            
            # get the values
            # audio_file_path = self.get_argument("audio_file",'')
            # text_file_path = self.get_argument("text_file",'')
            # print("audio_file_path: {}".format(audio_file_path))
            # print("text_file_path: {}".format(text_file_path))
            # audio_name = os.path.basename(audio_file_path)
            # text_name = os.path.basename(text_file_path)
            # print("audio, text name: {}/{}".format(audio_name, text_name))
            sr = self.get_argument("sr",16000)
            nj = self.get_argument("nj",1)
            no_word = self.get_argument("no_word",False)
            no_phone = self.get_argument("no_phone",False)
            # print(f"[information] audio_file: {audio_file_path}, nj: {nj}, no_word: {no_word}, no_phone: {no_phone}")
            
            # read and save auido file.
            # print("request.file: {}".format(self.request.files))
            audio_f = self.request.files.get('audio_file',[])
            text_f = self.request.files.get('text_file', [])
            audio_file_path = audio_f[0]['filename']
            text_file_path = text_f[0]['filename']
            print("audio_file_path: {}".format(audio_file_path))
            print("text_file_path: {}".format(text_file_path))
            audio_name = os.path.basename(audio_file_path)
            text_name = os.path.basename(text_file_path)
            print("audio, text name: {}/{}".format(audio_name, text_name))
            print(f"[information] audio_file: {audio_file_path}, nj: {nj}, no_word: {no_word}, no_phone: {no_phone}")
            if audio_f and text_f:
                # save auido file in a tmp directory and do FA.
                with tempfile.TemporaryDirectory() as tmpdirname:
                    print("generated tmp dir: {}".format(tmpdirname))
                    # save audio file
                    with wave.open(os.path.join(tmpdirname, audio_name), 'wb') as wav_file:
                        wav_file.setnchannels(AUDIO_CHANNEL)
                        wav_file.setsampwidth(AUDIO_SAMPLEWIDTH)
                        wav_file.setframerate(sr)
                        wav_file.writeframes(audio_f[0]['body'])
                    print(f"{audio_name} is successfully saved.")
                    # save text file.
                    print("text file: {}".format(text_f[0]['body'].decode('utf-8')))
                    with open(os.path.join(tmpdirname, text_name), 'w') as txt_file:
                        txt_file.write(text_f[0]['body'].decode('utf-8'))
                    print(f"{text_name} is successfully saved.")
                    
                    # do FA
                    bash_cmd = f"bash forced_align.sh {tmpdirname} -nj {nj}"
                    print("FA command line: {}".format(bash_cmd))
                    process = subprocess.Popen(bash_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    print("start FA")
                    process.wait()
                    print("FA DONE")
                    
                    # save result
                    print("save reuslt")
                    tg_file = f"{audio_name[:-4]}.TextGrid"
                    with open(tg_file, 'r') as tg:
                        SEND_FORM['result'] = tg.read()
            
            SEND_FORM['log'] = 'DONE!'
        except Exception as e:
            self.set_status(400)
            SEND_FORM['success'] = False
            SEND_FORM['log']= e
        finally:
            print("json to back: {}".format(SEND_FORM))
            self.write(json.dumps(SEND_FORM))
            
        

class App(Application):
    def __init__(self):
        handlers = [
            (r'/', FAtaskHandler),
        ]
        Application.__init__(self, handlers)

  
if __name__ == '__main__':
    app = App()
    app.listen(server_port)
    IOLoop.instance().start()


