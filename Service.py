#!/usr/bin/env python3
import psutil
import time
import subprocess
import shlex


def check_if_running(program, scriptname):
    for pid in psutil.pids():
        try:
            p = psutil.Process(pid)
            if program in p.name():

                for arg in p.cmdline():
                    if scriptname in str(arg):
                        return True
                    else:
                        pass
            else:
                pass
        except:
            continue


if check_if_running('python3', 'collect.py'):
    print('Exit Check Collect.py')

else:
    print('Ignite Alert')
    subprocess.Popen(shlex.split(
        "python3 /home/debian/lib/stocker/collect.py --uri mongodb://admin:admin123@localhost:27017/stocker --token 1177225094:AAGtBg9BzIJVVXHelSSYnaQB6HBhyG1obiQ"),
        shell=False, stdin=None, stdout=None, stderr=None, close_fds=True,)

if check_if_running('python3', 'stocker_alerts_bot.py'):
    print('Exit Check stocker_alerts_bot.py')
else:
    print('Ignite Telegram Bot')
    subprocess.Popen(shlex.split(
        "python3 /home/debian/lib/stocker/stocker_alerts_bot.py --uri mongodb://admin:admin123@localhost:27017/stocker --token 1177225094:AAGtBg9BzIJVVXHelSSYnaQB6HBhyG1obiQ"),
        shell=False, stdin=None, stdout=None, stderr=None, close_fds=True,)
