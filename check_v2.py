#!/usr/bin/python
import argparse
import os
import sys
import re
import datetime
import subprocess
import commands
import random
import time
import logging 
import heapq

def used_percentage():
        cmdStr="df | grep /data | awk '{print $5}'"
        used=commands.getoutput(cmdStr).strip('%')
	if used is None or used == '':
		cmdStr = "df | grep \"/$\" | awk '{print $5}'"
        	used=commands.getoutput(cmdStr).strip('%')
        return int(used)

def ensure_dir(directory):
        if not os.path.exists(directory):
                os.makedirs(directory)
		os.system("chown -R storageos:storageos " + directory)


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

## check if target is contained in fileName
## if not, also append it 
def containedInFile(target, fileName):
        found = False
        fp = open(fileName, "a+")
        for line in fp:
                if target in line:
                        found = True
                        break
        if not found:
                fp.write(target)
                fp.write("\n")
        fp.close()
        return found
def happenSameTime(whenStall, heapDumpInitiateDates, maxDiff):
        if whenStall is None or heapDumpInitiateDates is None or len(heapDumpInitiateDates) == 0:
                return False
        for when in heapDumpInitiateDates:
                diff = (whenStall - when).seconds
                if when < whenStall and diff < maxDiff:
                        return True
        return False

def humanfriendly(seconds):
	m, s = divmod(seconds, 60)
	h, m = divmod(m, 60)
	d, h = divmod(h, 24)
	if d > 0:
		return '%d days %d hours %d minutes %d seconds' % (d, h, m, s)
	elif h > 0:
		return '%d hours %d minutes %d seconds' % (h, m, s)
	elif m > 0:
		return '%d minutes %d seconds' % (m, s)
	else:
		return '%d seconds' % (s)

def isJFRRunning():
	checkJfrCmdStr='sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` JFR.check | grep "No available recordings"'
	status, output = commands.getstatusoutput(checkJfrCmdStr)
	if status == 0:
		return False
	return True

class JfrRecord:
	def __init__(self, ago, filename):
		self.ago = ago
		self.fileName = filename
	def __cmp__(self, o):
		return self.ago > o.ago

def pickJfrRecord(recentCount, whenStall):
	recentJfrFileCmdStr = "ls -ltrh /data/records/blob_auto.jfr* | egrep \"[0-9]$\" | awk '{print $9}'"
	status, output = commands.getstatusoutput(recentJfrFileCmdStr)
	result = []
	for name in output.splitlines():
		when = datetime.datetime.strptime(name.split('.')[-1], '%Y-%m-%d_%H:%M:%S')
		if when < whenStall and (whenStall - when).total_seconds() < (3600 * 12): # within last 12 hours
			heapq.heappush(result, JfrRecord(whenStall - when, name))
			if len(result) > recentCount:
				heapq.heappop(result)
	return [heapq.heappop(result) for i in range(len(result))]
		
	

########################################MAIN STARTS HERE#####################################################################################################################
RUNNING_FLAG_FILE = "/tmp/.check.py.running"
recordsDir="/data/records"
historyGcRecord="/tmp/historyGc.record"

## check if disk is full
ensure_dir(recordsDir)
if used_percentage() > 85:
	logging.info("Disk is almost full! Let's clean %s", recordsDir)
	os.system("rm -f /data/records/*") ## be carefull removing dir
	exit(-1)

## check if another instance is running
if os.path.isfile(RUNNING_FLAG_FILE):
    print "Another instance is already running!"
    exit(-2)
file(RUNNING_FLAG_FILE, 'w').write(str(os.getpid()))

try:
	logging.basicConfig(format='[%(asctime)s] %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
	parser = argparse.ArgumentParser(prog='PROG',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('--tdump', type=str2bool, default=False, help='thread dump')
	parser.add_argument('--gcdetect', type=str2bool, default=False, help='Java GC detect')
	parser.add_argument('--autoHeapDump', type=str2bool, default=False, help='Enable auto heap dump on JAVA GC stall')
	parser.add_argument('--autoJFR', type=str2bool, default=False, help='Enable auto JFR recording on JAVA GC stall')
	parser.add_argument('--rollingJFR', type=str2bool, default=False, help='Enable rolling JFR recording all the time')
	args = parser.parse_args()
	EnableThreadDump = args.tdump
	EnableGCDetect = args.gcdetect
	EnableAutoHeapDump = args.autoHeapDump
	EnableAutoJFR = args.autoJFR
	EnableRollingJFR = args.rollingJFR

	now  = datetime.datetime.now()
	suffix=now.strftime("%Y-%m-%d_%H:%M:%S")

	heapDumpFileFullPath = "%s/blob_auto.hprof.%s" % (recordsDir, suffix)
	threadDumpFileFullPath = "%s/blob_auto.threads.%s" % (recordsDir, suffix)
	jfrRecordFileFullPath = "%s/blob_auto.jfr.%s" % (recordsDir, suffix)
	## heapDumpCmd  = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` GC.heap_dump /var/log/blob_auto.hprof'
	fixedThreadDumpFileFullPath = "%s/blob_auto.threads" % (recordsDir)
	fixedThreadDumpCmd  = "sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` Thread.print > %s" % (fixedThreadDumpFileFullPath)
	## enableJfrCmd = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` VM.unlock_commercial_features'
	## jfrRecordCmd = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` JFR.start settings=profile duration=300s name=blob_auto.jfr filename=/var/log/blob_auto.jfr'

	heapDumpCmd  = "sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` GC.heap_dump -all %s" % (heapDumpFileFullPath)
	threadDumpCmd  = "sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` Thread.print > %s" % (threadDumpFileFullPath)
	enableJfrCmd = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` VM.unlock_commercial_features > /dev/null'
	jfrRecordCmd = "sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` JFR.start settings=profile duration=600s name=%s filename=%s" % (jfrRecordFileFullPath,jfrRecordFileFullPath)



	heapDumpInitiateFilterCmdStr="ls /opt/storageos/logs/blobsvc-gc-* -ltr | tail -n 1 | awk \'{print $9}\' | tr \'\\n\' '\\0' | xargs grep \'Heap Dump Initiated GC\'"
	heapDumpInitiateLogs=commands.getoutput(heapDumpInitiateFilterCmdStr)
	heapDumpInitiateDates = []
	tmr = re.compile("^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*")
	for line in heapDumpInitiateLogs.splitlines():
		if tmr.match(line) is None:
			continue
		when = datetime.datetime.strptime(line.split()[0][0:-6], '%Y-%m-%dT%H:%M:%S.%f')
		if when is not None:
			heapDumpInitiateDates.append(when)

	gcCmdStr="ls /opt/storageos/logs/blobsvc-gc-* -ltr | tail -n 1 | awk \'{print $9}\' | tr \'\\n\' '\\0' | xargs -0 -n1 /opt/storageos/tools/java_gc_stats 2>/dev/null"
	gcoutput = commands.getoutput(gcCmdStr)
	if EnableThreadDump :
		os.system("ip a | grep \"scope global public\" | awk \'{print $2}\'")
		#logging.info(gcoutput)
		os.system(fixedThreadDumpCmd)
		tfilterCmd = "echo \"    COUNT\tThread NAME\" && cat %s | grep \"^\\\"\" | awk -F\"-\" \'{print $1\"-\"$2}\' | sort 2>/dev/null | uniq -c | sort -nr 2>/dev/null | head -n 10" % (fixedThreadDumpFileFullPath)
		os.system(tfilterCmd)
		## detail of top 1
		tfilterCmd2 = "echo \"    BREAK DOWN FOR TOP 1\" && cat %s | grep \"^\\\"\" | awk -F\"-\" \'{print $1\"-\"$2}\' | sort 2>/dev/null | uniq -c | sort -nr 2>/dev/null| head -n 1 | awk -F\"\\\"\" \'{print $2}\' | xargs -I {} grep {} %s | awk -F\"-\" \'{print $1\"-\"$2\"-\"$3}\'| sort 2>/dev/null | uniq -c | sort -nr 2>/dev/null | head -n 10 2>/dev/null" % (fixedThreadDumpFileFullPath, fixedThreadDumpFileFullPath)
		os.system(tfilterCmd2)

	p = re.compile(".*Total time for which application threads were stopped: (\d+\.\d+) seconds.*")

	foundGcStall = 0
	for line in gcoutput.splitlines():
	    m = p.match(line)
	    if m is not None:
		whenStall = datetime.datetime.strptime(m.group(0).split()[0][0:-6], '%Y-%m-%dT%H:%M:%S.%f')
		if happenSameTime(whenStall, heapDumpInitiateDates, 180):
			#logging.info("JAVA GC stall at %s is caused by earlier Heap dump, hence ignored", whenStall)
			continue
		second = m.group(1)
		if float(second) > 10.0:
		    howLongAgo = (now - whenStall).total_seconds()
		    logging.info("JAVA GC stalled %s seconds happened %s ago around %s", second, humanfriendly(howLongAgo), whenStall)
		    if not containedInFile(m.group(0), historyGcRecord):
			if EnableGCDetect :
				logging.info("FOUND_GC_STALL over 10s!!!")
			os.system("ip a | grep \"scope global public\" | awk \'{print $2}\'")
			print m.group(0)
			foundGcStall = foundGcStall + 1
			if howLongAgo > 180:
				logging.info("JAVA GC stall happened %s ago, we are unable to capture the Heap or JFR in time that the stressing situation may have been gone", humanfriendly(howLongAgo))
			jfrRecords = pickJfrRecord(10, whenStall)
			for jfrRecord in jfrRecords:
				logging.info("JFR recorded : %s , recorded %s before the stall @%s", jfrRecord.fileName, humanfriendly(jfrRecord.ago.total_seconds()), whenStall)

	ableToCaptureGc = 0
	## Check if we hit GC "promotion failure" in last 10 seconds. Most likely when promotion failure happens, long GC stall usually follows.
	## checking tailing 1000 lines might not be enough? if so, increase the number. 
	foundPromotionFailure = 0
	checkPromotionFailureCmdStr = "ls /opt/storageos/logs/blobsvc-gc-* -ltr | tail -n 1 | awk \'{print $9}\' | tr \'\\n\' '\\0' | xargs -0 -I {} tail {} -n 1000 | grep \'promotion failed\' 2>/dev/null"
	promotionOutput = commands.getoutput(checkPromotionFailureCmdStr)
	p2 = re.compile("(\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d).*Allocation Failure.*")
	for line in promotionOutput.splitlines():
		m = p2.match(line)
		if m is not None:
			when = m.group(1)
			if (when is not None) and (not containedInFile(m.group(0), historyGcRecord)):
				foundPromotionFailure = foundPromotionFailure + 1
				whenPromotionFail = datetime.datetime.strptime(when, '%Y-%m-%dT%H:%M:%S')
				secondsAgo = (now - whenPromotionFail).total_seconds()
				if secondsAgo < 20:
					logging.info("Hit JAVA GC promotion failure %s ago around %s this time, try best to capture the Heap Dump", humanfriendly(secondsAgo), whenPromotionFail)
					ableToCaptureGc = ableToCaptureGc + 1 ## try best luck to capture the GC heap
					if EnableGCDetect :
						logging.info("potentially FOUND_GC_STALL because of promotion failure 20- seconds earlier!!!")
				else :
					logging.info("We may not able to capture GC for the promotion failure happened %s ago around %s this time", humanfriendly(secondsAgo), whenPromotionFail)
		

	if ableToCaptureGc > 0 and foundPromotionFailure > 0 :
		if EnableAutoHeapDump and (not happenSameTime(now, heapDumpInitiateDates, 3600)):
			## Just limit heap dump frequence as less than once per hour, to avoid performance impact since it causes GC stall.
			os.system(heapDumpCmd)
			logging.info("\nHeap dump (%s) has been generated.", heapDumpFileFullPath)
		if EnableAutoJFR:
			os.system(enableJfrCmd)
			if not isJFRRunning():
				os.system(jfrRecordCmd)
				logging.info("\nJFR record (%s) will be generated in 10 minutes for one shot", jfrRecordFileFullPath)
			else:
				logging.info("Skipped this JFR recording because another JFR record is still running")
		if EnableThreadDump :
			os.system("ip a | grep \"scope global public\" | awk \'{print $2}\'")
			os.system(threadDumpCmd)
	if EnableRollingJFR:
		os.system(enableJfrCmd)
		if not isJFRRunning():
			os.system(jfrRecordCmd)
			logging.info("\nJFR record (%s) will be generated in 10 minutes", jfrRecordFileFullPath)
		else:
			logging.info("Skipped this JFR recording because another JFR record is still running")
finally:
	os.unlink(RUNNING_FLAG_FILE)
