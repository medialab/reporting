#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Adapted from http://drandom.blogspot.fr/2012/02/python-convert-google-calendar-ics-to.html

import sys, re
from datetime import datetime
from datetime import date
from icalendar import Calendar
from urllib2 import urlopen
from dateutil import parser
from pytz import timezone
import codecs

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

#parse the ical
cal = Calendar.from_ical(cal)

# TIMEZONE management
tz= timezone(cal["X-WR-TIMEZONE"])
date1=tz.localize(date1)
date0=tz.localize(date0)

# processing variables
events = []
tags_hours_events={}
find_tags = re.compile(ur'(^|\W)#(\w+)',re.U)


for component in cal.walk():
    if component.name == "VEVENT":
        start_date = component.decoded('dtstart') if isinstance(component.decoded('dtstart'),datetime) else datetime.combine(component.decoded('dtstart'), date1.timetz())
        end_date = component.decoded('dtend') if isinstance(component.decoded('dtend'),datetime) else datetime.combine(component.decoded('dtend'), date1.timetz())
        

        if start_date < date0 or date1 < end_date:
            continue
        diff = end_date - start_date
        dur = diff.seconds/3600. + diff.days*7.3 #36.5h/week
     
        exp = component['summary'].replace('"', '""').strip()
        tags = []
        for _, tag in find_tags.findall(exp):
            #clean tag
            tag = tag.lower()
            if tag not in tags:
                tags.append(tag)
            if tag in tags_hours_events.keys():
                tags_hours_events[tag]=(tags_hours_events[tag][0]+dur,tags_hours_events[tag][1]+1)
            else:
                tags_hours_events[tag]=(dur,1)

        tags = u"|".join(tags)
        events.append([start_date.isoformat(), end_date.isoformat(), str(dur), exp, tags])

events.sort()
with codecs.open("events_duration_tag.csv","w",encoding="utf-8") as event_file :
    event_file.write("beginning,end,duration(h),summary,tags\n")
    for l in events:
        event_file.write(u",".join(l)+"\n")

#sort tags by hours duration
tags_hours_events_tuples=sorted(tags_hours_events.iteritems(), key=lambda i: i[1][0])
tags_hours_events_tuples.reverse()
total_duration = sum(_[1][0] for _ in tags_hours_events_tuples)
total_working_time = (date1 - date0).days/7.*36.5

print "tagged events represent %.2f"%(100*total_duration/total_working_time)

with codecs.open("tags_duration.csv","w",encoding="utf-8") as tag_file :
    tag_file.write("tag,duration(h),nb events\n")
    for (tag,(duration,nb_event)) in tags_hours_events_tuples:
        tag_file.write("%s,%s,%s\n"%(tag,duration,nb_event))

