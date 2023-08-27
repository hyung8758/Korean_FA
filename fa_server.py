"""
Korean_FA server.py: for web server.

Hyungwon Yang
23.08.07
"""

import sys

def main():
    usageMessage = f"Usage: {sys.argv[0]} (start|stop|status|version)"
    if len(sys.argv) == 2:
        from src.handlers.DaemonHandler import start, stop, status, version
        try:
            if sys.argv[1] == "start":
                start()
            elif sys.argv[1] == "stop":
                stop()
            elif sys.argv[1] == "status":
                status()
            elif sys.argv[1] == "version":
                version()
            else:
                print(usageMessage)
        except Exception as e:
            print(e)
    elif len(sys.argv) == 1:
        import tornado
        import yaml
        import src.handlers.DaemonHandler as dh
        from src.handlers.AlignHandler import AlignHandler
        from src.handlers.ServerHandler import App
        # config
        with open("conf/server.yaml") as f:
            server_config = yaml.load(f, Loader=yaml.FullLoader)
        app = App()
        server_port = server_config["server_port"]
        running_time = server_config["running_time"]
        app.listen(server_port)

        alignHandler = AlignHandler()
        alignHandler.getServerPort(server_port)
        # main job.
        main_fa_callback = tornado.ioloop.PeriodicCallback(alignHandler.process, running_time)
        main_fa_callback.start()
        tornado.ioloop.IOLoop.current().start()
    else:
        print(usageMessage)

if __name__ == "__main__":
    main()