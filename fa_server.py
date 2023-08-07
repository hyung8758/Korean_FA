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
    else:
        print(usageMessage)




if __name__ == "__main__":
    main()