#!/usr/bin/env python3
import psutil
import time
import subprocess
import shlex
import argparse


def main():
    args = get_args()

    if args.console:
        ignite_alert(args.uri, args.token)
    if args.console:
        ignite_telegram(args.uri, args.token)
    else:
        print("you must enter args -t Token and -u Uri")


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', dest='token', help='telegram token', default='')
    parser.add_argument('-u', dest='uri', help='uri for mango auth', default='')
    parser.add_argument('--console', help='check arg on console', default=False, action='store_true')
    return parser.parse_args()


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


def ignite_alert(uri, token):
    if check_if_running('python3', 'collect.py'):

        print('Exit Check Collect.py')
    else:
        print("Ignite alert")
        subprocess.Popen(shlex.split(
            "python3 /home/debian/lib/stocker/collect.py --uri " + uri + " --token " + token),
            shell=False, stdin=None, stdout=None, stderr=None, close_fds=True, )


def ignite_telegram(uri, token):
    if check_if_running('python3', 'stocker_alerts_bot.py'):
        print('Exit Check stocker_alerts_bot.py')

    else:
        print('Ignite Telegram Bot')
        subprocess.Popen(shlex.split(
            "python3 /home/debian/lib/stocker/stocker_alerts_bot.py --uri " + uri + " --token " + token),
            shell=False, stdin=None, stdout=None, stderr=None, close_fds=True, )


if __name__ == '__main__':
    main()
