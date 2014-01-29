#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Adapted from http://drandom.blogspot.fr/2012/02/python-convert-google-calendar-ics-to.html

import sys, re
from datetime import datetime
from icalendar import Calendar
from urllib2 import urlopen
from dateutil import parser

doc = """USAGE: ./get_ical_as_csv.py AGENDA_ICAL_URL [DATE0 [DATE1]]
- downloads the calendar at url AGENDA_ICAL_URL (should use private urls from Google Agenda)
- returns as CSV for all events if no date included
- returns as CSV events from DATE0 to today if only DATE0 given
- returns as CSV events from DATE0 to DATE1
(DATE0 & DATE1 should be ISO e.g. 2014-01-25 but other formats might work as well)
"""

if len(sys.argv) < 2:
    sys.stderr.write(doc)
    sys.exit(1)

url = sys.argv[1]
try:
    calfile = urlopen(url)
    cal = calfile.read()
except:
    sys.stderr.write('ERROR could not process data at url %s\n' % url)
    sys.exit(1)

date0 = parser.parse("2000-01-01")
date1 = parser.parse("3000-01-01")
try:
    if len(sys.argv) > 2:
        date0 = parser.parse(sys.argv[2])
        date1 = datetime.today()
    if len(sys.argv) > 3:
        d = parser.parse(sys.argv[3])
        if d > date0:
            date1 = d
        else:
            date1 = date0
            date0 = d
except:
    sys.stderr.write('ERROR could not process dates given in input %s\n' % sys.argv[2:])
    sys.exit(1)

# replace non-breakable spaces which break icalendar lib...
cal = cal.replace(' ', ' ')

find_tags = re.compile(r'(^|\W)#(\w+)')
res = []
cal = Calendar.from_ical(cal)
for component in cal.walk():
    if component.name == "VEVENT":
        st = datetime.combine(component.decoded('dtstart'), datetime.min.time())
        ed = datetime.combine(component.decoded('dtend'), datetime.min.time())
        if st < date0 or date1 < ed:
            continue
        diff = ed - st
        dur = diff.seconds/3600. + diff.days*24
        exp = '"%s"' % component['summary'].replace('"', '""').strip().encode('utf-8')
        tags = []
        for _, tag in find_tags.findall(exp):
            if tag not in tags:
                tags.append(tag)
        tags = "|".join(tags).encode('utf-8')
        res.append([st.isoformat(), ed.isoformat(), str(dur), exp])

res.sort()
print "beginning,end,summary,duration(h)"
for l in res:
    print ",".join(l)

