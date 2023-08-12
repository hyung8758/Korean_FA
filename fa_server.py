"""
Korean_FA server.py: for web server.

Hyungwon Yang
23.08.07
"""

import os, sys


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
        from src.handlers.ServerHandler import App
        # config
        with open("conf/server.yaml") as f:
            server_config = yaml.load(f, Loader=yaml.FullLoader)
        app = App()
        server_port = server_config["server_port"]
        app.listen(server_port)
        print("open server port: {}".format(server_port))

        tornado.ioloop.IOLoop.current().start()
    else:
        print(usageMessage)




if __name__ == "__main__":
    main()