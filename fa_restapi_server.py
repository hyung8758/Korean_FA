"""
Korean_FA restapi server.py: for restapi connection 

Hyungwon Yang
24.01.19
"""

import os, sys
import json
import wave
import signal
import tempfile
import subprocess
import logging
import argparse
import daemon
from daemon import pidfile
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

CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(CURRENT_PATH, "data")

AUDIO_CHANNEL = 1
AUDIO_SAMPLEWIDTH = 2

def sigint_handler(signal, frame):
    logging.info('Interrupted. Stop Processing.')
    sys.exit(0)
signal.signal(signal.SIGINT, sigint_handler)

def umask_type(value):
    try:
        # Convert the input string to an octal integer
        umask_value = int(value, 8)
        return umask_value
    except ValueError:
        raise argparse.ArgumentTypeError("Invalid umask value. Must be an octal number.")


class FAtaskHandler(RequestHandler):
    def get(self):
        pass

    def post(self):
        SEND_FORM = dict(success=True, log='', result='')
        try:
            # get the values
            sr = self.get_argument("sr",16000)
            nj = self.get_argument("nj",1)
            no_word = self.get_argument("no_word",False)
            no_phone = self.get_argument("no_phone",False)
            
            # read and save auido file.
            audio_f = self.request.files.get('audio_file',[])
            text_f = self.request.files.get('text_file', [])
            audio_file_path = audio_f[0]['filename']
            text_file_path = text_f[0]['filename']
            logging.info("audio_file_path: {}".format(audio_file_path))
            logging.info("text_file_path: {}".format(text_file_path))
            audio_name = os.path.basename(audio_file_path)
            text_name = os.path.basename(text_file_path)
            logging.info("audio, text name: {}/{}".format(audio_name, text_name))
            logging.info(f"[information] audio_file: {audio_file_path}, nj: {nj}, no_word: {no_word}, no_phone: {no_phone}")
            if audio_f and text_f:
                # save auido file in a tmp directory and do FA.
                with tempfile.TemporaryDirectory() as tmpdirname:
                    # save audio file
                    with wave.open(os.path.join(tmpdirname, audio_name), 'wb') as wav_file:
                        wav_file.setnchannels(AUDIO_CHANNEL)
                        wav_file.setsampwidth(AUDIO_SAMPLEWIDTH)
                        wav_file.setframerate(sr)
                        wav_file.writeframes(audio_f[0]['body'])
                    logging.info(f"{audio_name} is successfully saved.")
                    # save text file.
                    logging.info("text file: {}".format(text_f[0]['body'].decode('utf-8')))
                    with open(os.path.join(tmpdirname, text_name), 'w') as txt_file:
                        txt_file.write(text_f[0]['body'].decode('utf-8'))
                    logging.info(f"{text_name} is successfully saved.")
                    
                    # do FA
                    bash_cmd = f"bash forced_align.sh {tmpdirname} -nj {nj}"
                    if no_word:
                        bash_cmd += " -nw"
                    if no_phone:
                        bash_cmd += " -np"
                    logging.info("FA command: {}".format(bash_cmd))
                    process = subprocess.Popen(bash_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    logging.info("start FA")
                    process.wait()
                    logging.info("FA DONE")
                    
                    # save result
                    logging.info("save reuslt")
                    tg_file = f"{audio_name[:-4]}.TextGrid"
                    tg_file_path = os.path.join(tmpdirname,tg_file)
                    if os.path.exists(tg_file_path):
                        with open(tg_file_path, 'r') as tg:
                            SEND_FORM['result'] = tg.read()
                        SEND_FORM['log'] = 'DONE!'
                    else:
                        SEND_FORM['log'] = "FA was unsuccessful. Audio might be too long or noisy to force align."
                        SEND_FORM['success'] = False
        except Exception as e:
            self.set_status(400)
            SEND_FORM['success'] = False
            SEND_FORM['log']= str(e)
        finally:
            logging.info("json to back: {}".format(SEND_FORM))
            self.write(json.dumps(SEND_FORM))
            
        

class App(Application):
    def __init__(self):
        handlers = [
            (r'/', FAtaskHandler),
        ]
        Application.__init__(self, handlers)

def run_app(port: int,
            logformat: str,
            logfile: str):
    # logging.basicConfig(level=logging.INFO, format=logformat, filename=logfile)
    app = App()
    app.listen(port)
    logging.info("Open PORT: {}".format(port))
    IOLoop.instance().start()

def start_daemon(daemon_pidfile:str, 
               port:int,
               logformat:str,
               logfile:str,
               file_logger:logging.FileHandler,
               working_directory:str='/tmp',
               umask:umask_type=0o002):
    with daemon.DaemonContext(
                    working_directory = working_directory,
                    umask = umask,
                    pidfile = pidfile.TimeoutPIDLockFile(daemon_pidfile),
                    files_preserve=[file_logger.stream.fileno()]
                    ):
        run_app(port=port,
                logformat=logformat,
                logfile=logfile)
    
def stop_daemon(daemon_pidfile: str,
                logformat:str,
                logfile:str):
    # logging.basicConfig(level=logging.INFO, format=logformat, filename=logfile)
    try:
        with open(daemon_pidfile, 'r') as pidfile:
            pid = int(pidfile.read().strip())
        logging.info(f"Stopping daemon with PID: {pid}")
        # Send a SIGTERM signal to the daemon
        signal.signal(signal.SIGTERM, signal.SIG_IGN)  # Ignore SIGTERM while checking
        os.kill(pid, signal.SIGTERM)
    except FileNotFoundError:
        logging.info("Cannot find running daemon.")
    except ProcessLookupError:
        logging.info("Daemon not running.")    

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",
                        type=int,
                        default=31065,
                        help="FA api server port.")
    parser.add_argument("action",
                        choices=['start', 'stop', 'standalone'],
                        help="Action for start or stop FA api server daemon. standalone for running the server right away.")
    parser.add_argument("--working_directory",
                        type=str,
                        default=CURRENT_PATH,
                        help="daemon working directory")
    parser.add_argument("--umask",
                        type=umask_type,
                        default=0o002,
                        help="daemon umask")
    parser.add_argument("--pidfile",
                        type=str,
                        default=os.path.join(CURRENT_PATH,".pid/fa_restapi.pid"))
    parser.add_argument("--logfile",
                        type=str,
                        default=os.path.join(CURRENT_PATH,"log/fa_restapi.log"))
    parser.add_argument("--logformat",
                        type=str,
                        default="%(asctime)s(%(module)s:%(lineno)d)%(levelname)s:%(message)s")
    
    args = parser.parse_args()
    
    # directory 생성
    logdir = os.path.dirname(args.logfile)
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    piddir = os.path.dirname(args.pidfile)
    if not os.path.exits(piddir):
        os.makedirs(piddir)
    
    print("LOG path: {}".format(args.logfile))
    # handling logger
    logging.basicConfig(level=logging.INFO, format=args.logformat)
    file_logger = logging.FileHandler(args.logfile, "a")
    logger = logging.getLogger()
    logger.addHandler(file_logger)
    
    if args.action == 'start':
        # start가 여러번 발생해도 중복실행 안함.
        start_daemon(daemon_pidfile=args.pidfile,
                     port=args.port,
                     logformat=args.logformat,
                     logfile=args.logfile,
                     working_directory=args.working_directory,
                     umask=args.umask,
                     file_logger=file_logger
                     )
    elif args.action == 'stop':
        stop_daemon(daemon_pidfile=args.pidfile,
                    logformat=args.logformat,
                    logfile=args.logfile)
    else:
        print("Open PORT: {}".format(args.port))
        run_app(port=args.port,
                logformat=args.logformat,
                logfile=args.logfile)

