#!/usr/bin/python
f = open('olddata.log','r')
d1 = {}
for line in f.readlines():
	if line is None:
		continue
	words=line.split()
	subd = dict(avg=words[2],max=words[4],deviation=words[6])
	d1[words[0]] = subd
f.close()

f = open('newdata.log','r')
d2 = {}
for line in f.readlines():
	if line is None:
		continue
	words=line.split()
	subd = dict(avg=words[2],max=words[4],deviation=words[6])
	d2[words[0]] = subd
f.close()

tags=['avg','max','deviation']
for key in d2:
	if not d1.has_key(key):
		continue
	for tag in tags:
		#print type(d1[key][tag])
		if long(float(d1[key][tag])) < long(float(d2[key][tag])):
			print key, "degraded ", d1[key][tag]," => ", d2[key][tag]

