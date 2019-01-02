import time
import subprocess

def runCommand(cmd):
    result = subprocess.check_output(cmd, shell=True)
    return result.decode("utf-8")

top=runCommand("top -n 1 -p `pidof yourprocessname`")

print top
