#!/usr/bin/python
import os
import sys
import re
import datetime
import subprocess
import commands
import random
import time

def used_percentage():
	cmdStr="df | grep /data | awk '{print $5}'"
	used=commands.getoutput(cmdStr).strip('%')
	return int(used)
	
def ensure_dir(file_path):
	directory = os.path.dirname(file_path)
	if not os.path.exists(directory):
		os.makedirs(directory)

def previous_hour(minus):
	lasttime = str(datetime.datetime.now() - datetime.timedelta(hours=minus)).split()
	lastday=lasttime[0].split('-')
	hour=lasttime[1].split(':')[0]
	year, month, day = lastday[0], lastday[1], lastday[2]
	return year, month, day, hour
def previous_day(minus):
	lastday = str(datetime.date.today() - datetime.timedelta(minus)).split()[0].split('-')
	year, month, day = lastday[0], lastday[1], lastday[2]
	return year, month,day

INTERVAL_IN_HOURS=12
RETAIN_DAYS=4
SOURCE_DIR='/opt/storageos/logs/'
TARGET_DIR='/data/logfile_backup/'
LOGFILES=['metering-error.log','metering-btree-dump.log', 'blobsvc-error.log', 'blobsvc-btree-dump.log', 'rm.log', 'rm-error.log']

if used_percentage() > 85:
	print "Disk is almost full!"
	exit(-1)

ensure_dir(TARGET_DIR)

for h in range(2, 2 + INTERVAL_IN_HOURS):
	year, month, day, hour = previous_hour(h)
	print "Backing up logfiles yesterday to {} {}{}{}-{}".format(TARGET_DIR, year, month, day,hour)
	for name in LOGFILES:
		filename="{}{}.{}{}{}-{}*.gz".format(SOURCE_DIR, name, year, month, day, hour)
		copyCmd="cp -n {} {}".format(filename, TARGET_DIR)
		os.system(copyCmd)

year, month, day = previous_day(RETAIN_DAYS)
print "Removing logfiles {} days ago {}{}{}".format(RETAIN_DAYS, year, month, day)
# remove outdated logfs
for name in LOGFILES:
	filename="{}.{}{}{}-*.gz".format(name, year, month, day)
	rmCmd="rm -f {}{}".format(TARGET_DIR,filename)
	os.system(rmCmd)
