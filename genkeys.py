#!/usr/bin/python
TOTAL_KEY_COUNT=10000000
VALUE_LEN = 512
## len = 128
MAGIC_STR="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$";
STR_LIST = []
for i in range(0, VALUE_LEN / len(MAGIC_STR)):
    STR_LIST.append(MAGIC_STR);
VALUE_STR = ''.join(STR_LIST)

print len(VALUE_STR)
print VALUE_STR

filename = "testkey.log"
f=open(filename,'w')
for i in range(0, TOTAL_KEY_COUNT):
    f.write("put /testdir/key%d %s\n" % (i, VALUE_STR))
