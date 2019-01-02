#!/usr/bin/python
import os
import sys
import re
import datetime
import subprocess
import commands
import random
import time


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
def happenSameTime(whenStall, heapDumpInitiateDates):
        if whenStall is None or heapDumpInitiateDates is None or len(heapDumpInitiateDates) == 0:
                return False
        for when in heapDumpInitiateDates:
                diff = (whenStall - when).seconds
                if when > whenStall:
                        diff = (when - whenStall).seconds
                if(diff < 180) :
                        return True
        return False

import argparse
parser = argparse.ArgumentParser(prog='PROG',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--tdump', type=str2bool, default=False, help='thread dump')
parser.add_argument('--gcdetect', type=str2bool, default=False, help='Java GC detect')
parser.add_argument('--autoHeapDump', type=str2bool, default=False, help='Enable auto heap dump on JAVA GC stall')
parser.add_argument('--autoJFR', type=str2bool, default=False, help='Enable auto JFR recording on JAVA GC stall')
args = parser.parse_args()
EnableThreadDump = args.tdump
EnableGCDetect = args.gcdetect
EnableAutoHeapDump = args.autoHeapDump
EnableAutoJFR = args.autoJFR

## thread dump command
historyGcRecord="/tmp/historyGc.record"
heapDumpCmd  = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` GC.heap_dump /var/log/blob_auto.hprof'
threadDumpCmd  = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` Thread.print > /var/log/blob_auto.threads'
enableJfrCmd = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` VM.unlock_commercial_features'
jfrRecordCmd = 'sudo -u storageos /usr/lib64/jvm/java-1.8.0-oracle/bin/jcmd `pidof blobsvc` JFR.start settings=profile name=blob_auto.jfr filename=/var/log/blob_auto.jfr duration=600s'

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

gcCmdStr="ls /opt/storageos/logs/blobsvc-gc-* -ltr | tail -n 1 | awk \'{print $9}\' | tr \'\\n\' '\\0' | xargs -0 -n1 /opt/storageos/tools/java_gc_stats"
gcoutput = commands.getoutput(gcCmdStr)
if EnableThreadDump :
        os.system("ip a | grep \"inet 10.249\" | awk \'{print $2}\'")
        print gcoutput
        os.system(threadDumpCmd)
        tfilterCmd = "echo \"    COUNT\tThread NAME\" && cat /var/log/blob_auto.threads | grep \"^\\\"\" | awk -F\"-\" \'{print $1\"-\"$2}\' | sort | uniq -c | sort -nr | head -n 10"
        os.system(tfilterCmd)

p = re.compile(".*Total time for which application threads were stopped: (\d+\.\d+) seconds.*")

foundGcStall = 0
for line in gcoutput.splitlines():
    m = p.match(line)
    if m is not None:
        whenStall = datetime.datetime.strptime(m.group(0).split()[0][0:-6], '%Y-%m-%dT%H:%M:%S.%f')
        if happenSameTime(whenStall, heapDumpInitiateDates):
                print "GC stall is caused by Heap dump ",whenStall
                continue
        second = m.group(1)
        if float(second) > 10.0:
            if not containedInFile(m.group(0), historyGcRecord):
		if EnableGCDetect :
                	print "FOUND_GC_STALL over 10s!!!";
                os.system("ip a | grep \"inet 10.249\" | awk \'{print $2}\'")
                print m.group(0)
                foundGcStall = foundGcStall + 1

if foundGcStall > 0 :
	if EnableAutoHeapDump :
        	os.system(heapDumpCmd)
        	print "\nHeap dump (/var/log/blob_auto.hprof) has been generated."
	if EnableAutoJFR :
        	os.system(enableJfrCmd)
        	os.system(jfrRecordCmd)
		print "\nJFR record (/var/log/blob_auto.jfr) will be captured in 10 minutes."

## Try to catch "dumping to index hit exception"
## This occurs every two hours and checks the log files of last two hours.
timeNow = datetime.datetime.now()
if int(str(timeNow).split(" ")[1].split(":")[0]) % 2 == 0 and int(str(timeNow).split(" ")[1].split(":")[1]) > 20:

    StartPoint1 = timeNow - datetime.timedelta(hours = 2)
    SearchTimeStartPointForDump = int(str(StartPoint1).split(" ")[0].split("-")[0] + str(StartPoint1).split(" ")[0].split("-")[1] + str(StartPoint1).split(" ")[0].split("-")[2] + str(StartPoint1).split(" ")[1].split(".")[0].split(":")[0] + str(StartPoint1).split(" ")[1].split(".")[0].split(":")[1] + str(StartPoint1).split(" ")[1].split(".")[0].split(":")[2])
    DumpHitExceptionCmd1 = "ls /var/log/blobsvc-btree-dump* -ltr | awk \'{print $9}\' > /tmp/DumpHitExceptionFileList.tmp"
    os.system(DumpHitExceptionCmd1)
    flist = open("/tmp/DumpHitExceptionFileList.tmp", "a+")
    dumpCheckList = open("/tmp/DumpCheckList.tmp", "a+")

    for line in flist:
        if "2018" in line:
            timeOfFile = int(line.split(".")[2].split("-")[0] + line.split(".")[2].split("-")[1])
            if timeOfFile > SearchTimeStartPointForDump:
                dumpCheckList.write(line)
        if "blobsvc-btree-dump.log" in line and "2018" not in line:
            dumpCheckList.write(line)
    flist.close()
    dumpCheckList.close()

    DumpHitExceptionCmd2 = "grep \"blobsvc-btree-dump\" /tmp/DumpCheckList.tmp | xargs zgrep -A 5 \"dumping to index hit exception\" | tail -n 6 "
    DumpHitExceptionOut = commands.getoutput(DumpHitExceptionCmd2)
    os.system("rm -rf /tmp/DumpHitExceptionFileList.tmp")
    os.system("rm -rf /tmp/DumpCheckList.tmp")
    if (DumpHitExceptionOut is not None) and DumpHitExceptionOut != '':
        print "\nDumping to index hit exception!";os.system("ip a | grep \"inet 10.249\" | awk \'{print $2}\'")
        print "\nThe latest logs:"
        print(DumpHitExceptionOut)

    if int(str(timeNow).split(" ")[1].split(":")[0]) % 4 == 0:
        
        ## Try to catch DT Init
        ## This occurs every four hours and checks the log files of last four hours
        StartPoint2 = timeNow - datetime.timedelta(hours = 4)
        SearchTimeStartPointForInit = int(str(StartPoint2).split(" ")[0].split("-")[0] + str(StartPoint2).split(" ")[0].split("-")[1] + str(StartPoint2).split(" ")[0].split("-")[2] + str(StartPoint2).split(" ")[1].split(".")[0].split(":")[0] + str(StartPoint2).split(" ")[1].split(".")[0].split(":")[1] + str(StartPoint2).split(" ")[1].split(".")[0].split(":")[2])
        DTInitCmd1 = "ls /var/log/blobsvc-btree-dump* -ltr | awk \'{print $9}\' > /tmp/DTInitFileList.tmp"
        os.system(DTInitCmd1)
        flist2 = open("/tmp/DTInitFileList.tmp", "a+")
        DTInitCheckList = open("/tmp/DTInitCheckList.tmp", "a+")

        for line in flist2:
            if "2018" in line:
                timeOfFile = int(line.split(".")[2].split("-")[0] + line.split(".")[2].split("-")[1])
                if timeOfFile > SearchTimeStartPointForInit:
                    DTInitCheckList.write(line)
            if "blobsvc-btree-dump.log" in line and "2018" not in line:
                DTInitCheckList.write(line)
        flist2.close()
        DTInitCheckList.close()
 
        DTInitCmd2 = "grep \"blobsvc-btree-dump\" /tmp/DTInitCheckList.tmp | xargs zgrep -A 2 \"start taking over the ownership\" | tail -n 3 "
        DTInitOut = commands.getoutput(DTInitCmd2)
        os.system("rm -rf /tmp/DTInitFileList.tmp")
        os.system("rm -rf /tmp/DTInitCheckList.tmp")
        if (DTInitOut is not None) and DTInitOut != '': 
            print "\nDT init occurred!";os.system("ip a | grep \"inet 10.249\" | awk \'{print $2}\'")
            print "\nThe latest logs:"
            print(DTInitOut)

        ## Btree iterate occurs every four hours on only one node of each zone.
        getIPCmd = "ip a | grep \"10.249\" | awk \'{print $2}\' | cut -d \'/\' -f1"
        getIPOut = commands.getoutput(getIPCmd)
        if '.173' in getIPOut or '.87' in getIPOut:
            getOBLink = "http://" + getIPOut + ":9101/diagnostic/OB/0/?useStyle=xsl"
            getLSLink = "http://" + getIPOut + ":9101/diagnostic/LS/0/?useStyle=xsl"
            os.environ['getOBLink'] = str(getOBLink)
            os.environ['getLSLink'] = str(getLSLink)
            OBLinkCmd = "curl -s $getOBLink | cut -d \">\" -f6 | cut -d \"<\" -f1 | tail -n 1"
            LSLinkCmd = "curl -s $getLSLink | cut -d \">\" -f6 | cut -d \"<\" -f1 | tail -n 1"
            OBLinkOut = commands.getoutput(OBLinkCmd)
            LSLinkOut = commands.getoutput(LSLinkCmd)

            os.environ['OBLinkOut'] = str(OBLinkOut)
            OBLink1Cmd = "echo $OBLinkOut | cut -d \"_\" -f 1-3"
            OBLink1Out = commands.getoutput(OBLink1Cmd)
            OBLink2Cmd = "echo $OBLinkOut | cut -d \"_\" -f 5-"
            OBLink2Out = commands.getoutput(OBLink2Cmd)

            os.environ['LSLinkOut'] = str(LSLinkOut)
            LSLink1Cmd = "echo $LSLinkOut | cut -d \"_\" -f 1-3"
            LSLink1Out = commands.getoutput(LSLink1Cmd)
            LSLink2Cmd = "echo $LSLinkOut | cut -d \"_\" -f 5-"
            LSLink2Out = commands.getoutput(LSLink2Cmd)

            if '.17' in getIPOut:
                zone = "urn:storageos:VirtualDataCenterData:7bc9cd0c-43a3-49b8-bd9f-2b637f9c48a7"
            elif '.8' in getIPOut:
                zone = "urn:storageos:VirtualDataCenterData:52cb45b2-98b8-4a6a-b812-5150b103ab14"

            if '.17' in getIPOut:
                print("\n******Btree Iterate Result******")
                print("10.249.249.171-174:")
                for dtType in (0,1):
                    if dtType == 0:
                        Link1Out = OBLink1Out
                        Link2Out = OBLink2Out
                    else:
                        Link1Out = LSLink1Out
                        Link2Out = LSLink2Out
                    firstNum = random.randint(0,24)
                    secondNum = random.randint(25,49)
                    thirdNum = random.randint(50,74)
                    fourthNum = random.randint(75,99)
                    fifthNum = random.randint(100,127)
                    for i in (firstNum, secondNum, thirdNum, fourthNum, fifthNum):
                        dtID = Link1Out + "_" + str(i) + "_" + Link2Out
                        iterateBtreePath1 = "http://10.249.249.171:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath1'] = str(iterateBtreePath1)
                        iterateBtreeCmd1 = "curl -s $iterateBtreePath1 | wc -l"
                        iterateBtreeOut1 = commands.getoutput(iterateBtreeCmd1)
                        iterateBtreePath2 = "http://10.249.249.172:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath2'] = str(iterateBtreePath2)
                        iterateBtreeCmd2 = "curl -s $iterateBtreePath2 | wc -l"
                        iterateBtreeOut2 = commands.getoutput(iterateBtreeCmd2)
                        iterateBtreePath3 = "http://10.249.249.173:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath3'] = str(iterateBtreePath3)
                        iterateBtreeCmd3 = "curl -s $iterateBtreePath3 | wc -l"
                        iterateBtreeOut3 = commands.getoutput(iterateBtreeCmd3)
                        iterateBtreePath4 = "http://10.249.249.174:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath4'] = str(iterateBtreePath4)
                        iterateBtreeCmd4 = "curl -s $iterateBtreePath4 | wc -l"
                        iterateBtreeOut4 = commands.getoutput(iterateBtreeCmd4)
                        for rowNum in iterateBtreeOut1,iterateBtreeOut2,iterateBtreeOut3,iterateBtreeOut4:
                            if rowNum != '0':
                                if dtType == 0:
                                    print("OB_" + str(i) + ": page number = " + rowNum)
                                else:
                                    print("LS_" + str(i) + ": page number = " + rowNum)
                    print("")
'''
            elif '.8' in getIPOut:
                print("\n******Btree Iterate Result******")
                print("10.249.229.85-88:")
                for dtType in (0,1):
                    if dtType == 0:
                        Link1Out = OBLink1Out
                        Link2Out = OBLink2Out
                    else:
                        Link1Out = LSLink1Out
                        Link2Out = LSLink2Out
                    for j in range(128):
                        dtID = Link1Out + "_" + str(j) + "_" + Link2Out
                        iterateBtreePath1 = "http://10.249.229.85:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath1'] = str(iterateBtreePath1)
                        iterateBtreeCmd1 = "curl -s $iterateBtreePath1 | wc -l"
                        iterateBtreeOut1 = commands.getoutput(iterateBtreeCmd1)
                        iterateBtreePath2 = "http://10.249.229.86:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath2'] = str(iterateBtreePath2)
                        iterateBtreeCmd2 = "curl -s $iterateBtreePath2 | wc -l"
                        iterateBtreeOut2 = commands.getoutput(iterateBtreeCmd2)
                        iterateBtreePath3 = "http://10.249.229.87:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath3'] = str(iterateBtreePath3)
                        iterateBtreeCmd3 = "curl -s $iterateBtreePath3 | wc -l"
                        iterateBtreeOut3 = commands.getoutput(iterateBtreeCmd3)
                        iterateBtreePath4 = "http://10.249.229.88:9101/btreeIterate/" + dtID + "/" + zone + "/-1/false/ture/1/0"
                        os.environ['iterateBtreePath4'] = str(iterateBtreePath4)
                        iterateBtreeCmd4 = "curl -s $iterateBtreePath4 | wc -l"
                        iterateBtreeOut4 = commands.getoutput(iterateBtreeCmd4)
                        for rowNum in iterateBtreeOut1,iterateBtreeOut2,iterateBtreeOut3,iterateBtreeOut4:
                            if rowNum != '0':
                                if dtType == 0:
                                    print("OB_" + str(j) + ": page number = " + rowNum)
                                else:
                                    print("LS_" + str(j) + ": page number = " + rowNum)
                    print("")
'''
