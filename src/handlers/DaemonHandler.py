"""
DaemonHandler: control daemon server

Hyungwon Yang
23.08.07
"""


import sys, os, time, psutil, signal
import argparse
import logging
import tornado
import yaml

from src.handlers.ServerHandler import App
from src.handlers.AlignHandler import AlignHandler

# config
with open("conf/server.yaml") as f:
    server_config = yaml.load(f, Loader=yaml.FullLoader)
parser = argparse.ArgumentParser()
args =  parser.parse_args(namespace=argparse.Namespace(**server_config))
_version = args.version
CURRENT_PATH = "/".join([os.path.dirname(os.path.abspath(__file__)), "../.."])

# variables
pauseRunLoop = 0    # 0 means none pause between the calling of run() method.
restartPause = 1    # 0 means without a pause between stop and start during the restart of the daemon
waitToHardKill = 3  # when terminate a process, wait until kill the process with SIGTERM signal

isReloadSignal = False
canDaemonRun = True
processName = os.path.basename(sys.argv[0])
stdin = '/dev/null'
stdout = '/dev/null'
stderr = '/dev/null'

# pid
pid_dir = args.server_pid_path
pid_path = os.path.join(CURRENT_PATH, pid_dir)
server_pidfile = args.server_pidfile
if not os.path.exists(pid_path):
    os.makedirs(pid_path)
# pid folder가 있을경우만 pid 파일 생성.
pid_file = os.path.join(pid_path, server_pidfile)

# data : save uploaded and processed data(wav, txt, TextGrid)
data_dir = args.data_path
data_path = os.path.join(CURRENT_PATH, data_dir)
if not os.path.exists(data_path):
    os.makedirs(data_path)

# history log
history_dir = args.history_path
history_path = os.path.join(CURRENT_PATH, history_dir)
if not os.path.exists(history_path):
    os.makedirs(history_path)

# make pid file.
def savePidFile(pid, saveName: str):
    if ".pid" in saveName:
        savePath = os.path.join(pid_path, saveName)
    else:
        savePath = os.path.join(pid_path, saveName + ".pid")
    with open(savePath, 'w', encoding='utf-8') as wrt:
        wrt.write(str(pid)+"\n")

# remove pid file.
def removePidFile(fileName: str):
    if ".pid" in fileName:
        filePath = os.path.join(pid_path, fileName)
    else:
        filePath = os.path.join(pid_path, fileName + ".pid")
    if os.path.exists(filePath):
        os.remove(filePath)
        
def run():
    # open connection.
    app = App()
    app.listen(args.server_port)
    print("open server port: {}".format(args.server_port))
    server_pid = os.getpid()
    savePidFile(server_pid, server_pidfile)
    
    alignHandler = AlignHandler()
    alignHandler.getServerPort(args.server_port)
    
    # main job.
    main_fa_callback = tornado.ioloop.PeriodicCallback(alignHandler.process, args.running_time)
    main_fa_callback.start()

    tornado.ioloop.IOLoop.current().start()


def on_terminate(process):
        m = f"The daemon process with PID {process.pid} has ended correctly."
        logging.info(m)
        print(m)

def _sigterm_handler(signum, frame):
    canDaemonRun = False

def _reload_handler(signum, frame):
    isReloadSignal = True

def _makeDaemon():
        """
        Make a daemon, do double-fork magic.
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent.
                sys.exit(0)
        except OSError as e:
            m = f"Fork #1 failed: {e}"
            logging.error(m)
            print(m)
            sys.exit(1)

        # Decouple from the parent environment.
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Do second fork.
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent.
                sys.exit(0)
        except OSError as e:
            m = f"Fork #2 failed: {e}"
            logging.error(m)
            print(m)
            sys.exit(1)

        m = "The daemon process is going to background."
        logging.info(m)
        print(m)

        # Redirect standard file descriptors.
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(stdin, 'r')
        so = open(stdout, 'a+')
        se = open(stderr, 'a+')
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        
def _infiniteLoop():
    try:
        if pauseRunLoop:
            time.sleep(pauseRunLoop)

            while canDaemonRun:
                run()
                time.sleep(pauseRunLoop)
        else:
            while canDaemonRun:
                run()

    except Exception as e:
        m = f"Run method failed: {e}"
        sys.stderr.write(m)
        sys.exit(1)

def getPidFiles():
    dir_list = os.listdir(pid_path)
    pid_file_list = [each_list for each_list in dir_list if ".pid" in each_list]
    return pid_file_list

def getPids(pid_file_list):
    pid_list = dict()
    for each_file in pid_file_list:
        with open(os.path.join(pid_path, each_file), 'r', encoding='utf-8') as txt:
            pid_line = txt.read().strip()
            pid_list[each_file] = pid_line
    return pid_list

def start():
    # Handle signals
    signal.signal(signal.SIGINT, _sigterm_handler)
    signal.signal(signal.SIGTERM, _sigterm_handler)
    signal.signal(signal.SIGHUP, _reload_handler)

    # Check if the daemon is already running.
    pid_file_list = getPidFiles()

    if server_pidfile in pid_file_list:
        pid_list = getPids(pid_file_list)
        server_pid = pid_list[server_pidfile]
        print(f"Find a previous daemon processes with PIDs {server_pid}. Is not already the daemon running?")
        sys.exit(1)
    else:
        print(f"Start the daemon version {_version}")

    # Daemonize the main process
    _makeDaemon()
    # Start a infinitive loop that periodically runs run() method
    _infiniteLoop()

def stop():
    pid = 999999
    logging.info("stop daemon.")
    print("stop daemon.")
    try:
        # find pid file list.
        pid_file_list = getPidFiles()
        if pid_file_list == []:
            print("Cannot find any daemon process.")
            return None
        
        # get process id
        logging.info(f"Found process ids: {pid_file_list}")
        print(f"Found process ids: {pid_file_list}")
        pid_list = getPids(pid_file_list)
        # kill process
        if pid_list:
            for pid_k in pid_list.keys():
                pid = int(pid_list[pid_k])
                if psutil.pid_exists(pid):
                    p = psutil.Process(pid)
                    p.terminate()
                    gone, alive = psutil.wait_procs([p], timeout=3, callback=on_terminate)
                    
                    for p in alive:
                        p.kill()
                        print(f"The daemon process with PID {p.pid} was killed with SIGTERM!")
                else:
                    m = f"{pid} pid does not exist."
                    logging.warning(m)
                    print(m)
                removePidFile(pid_k)
        else:
            print("Cannot find any daemon process.")
    except Exception as e:
        print(e)
        
def status():
    """
    Get status of the daemon.
    """

    pid_list = getPidFiles()

    if server_pidfile in pid_list:
        server_pids = getPids([server_pidfile])
        logging.info(f"The daemon is running with PID {server_pids[server_pidfile]}.")
        print(f"The daemon is running with PID {server_pids[server_pidfile]}.")
    else:
        logging.info("The daemon is not running!")
        print("The daemon is not running!")

def version():
    print(f"The daemon version: {_version}")
