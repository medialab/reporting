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
import json

doc = """USAGE: ./get_ical_as_csv.py [DATE0 [DATE1]]
- read icals.json as configuration file with ical urls (should use private urls from Google Agenda)
- downloads the calendar specified
- writes to events_duration_tag.csv for all events if no date included
- writes to events_duration_tag.csv from DATE0 to today if only DATE0 given
- writes to events_duration_tag.csv from DATE0 to DATE1
- extracts keyword formated as hashtags #keyword
- writes duration agregated by keywords to tags_duration.csv
(DATE0 & DATE1 should be ISO e.g. 2014-01-25 but other formats might work as well)
"""

if len(sys.argv) >=2 and sys.argv[1]=="-h":
    sys.stderr.write(doc)
    sys.exit(1)




date0 = parser.parse("2000-01-01")
date1 = parser.parse("3000-01-01")
try:
    if len(sys.argv) > 1:
        date0 = parser.parse(sys.argv[1])
        date1 = datetime.today()
    if len(sys.argv) > 2:
        d = parser.parse(sys.argv[2])
        if d > date0:
            date1 = d
        else:
            date1 = date0
            date0 = d
except:
    sys.stderr.write('ERROR could not process dates given in input %s\n' % sys.argv[2:])
    sys.exit(1)

conf=json.load(codecs.open("icals.json","r",encoding="UTF8"))
try:
    pass
except:
    sys.stderr.write('ERROR could not retrieve configuration file  icals.json\n')
    sys.exit(1)  

all_tags={}

for people in conf:
    if "ical_url" not in people.keys():
        continue
    url=people["ical_url"]
    print "start processing %s"%people["name"]
    # retrieve ical file from URL
    try:
        calfile = urlopen(url)
        cal = calfile.read()
    except:
        sys.stderr.write('ERROR could not process data at url %s\n' % url)
        sys.exit(1)



    # replace non-breakable spaces which break icalendar lib...
    cal = cal.replace(' ', ' ')

    #parse the ical
    cal = Calendar.from_ical(cal)

    # TIMEZONE management
    tz= timezone(cal["X-WR-TIMEZONE"])
    try:
        date1=tz.localize(date1)
        date0=tz.localize(date0)
        #will raise if done twice..

    except:
        pass
    # processing variables
    events = []
    tags_hours_events={}
    regexp=people.get("regexp")
    if regexp:
        find_tags = re.compile(regexp,re.U)
    else:
        find_tags = re.compile(ur'(^|\W)#(\w+)',re.U)

    projects_tags=dict((t,(0,0)) for t in people.get("projects").split(",")) if "projects" in people.keys() else {}
    activities_tags=dict((t,(0,0)) for t in people["activities"].split(",")) if "activities" in people.keys() else {}
    ignore_tags=people["ignore"].split(",") if "ignore" in people.keys() else []
    unknown_tags={}

    tagged_dur=0

    for component in cal.walk():
        if component.name == "VEVENT":
            start_date = component.decoded('dtstart') if isinstance(component.decoded('dtstart'),datetime) else datetime.combine(component.decoded('dtstart'), date1.timetz())
            end_date = component.decoded('dtend') if isinstance(component.decoded('dtend'),datetime) else datetime.combine(component.decoded('dtend'), date1.timetz())
            

            if start_date < date0 or date1 < end_date:
                continue
            diff = end_date - start_date
            dur = diff.seconds/3600. + diff.days*7.3 #36.5h/week
         
            exp = component['summary'].replace('"', '""').strip()

            event_projects_tags=[]
            event_activities_tags=[]
            event_unknown_tags=[]

            tagged=False
            for _, tag in find_tags.findall(exp):
                #clean tag
                tag = tag.lower()
                # multi tag management 
                
                if tag in projects_tags.keys() :
                    event_projects_tags.append(tag)
                    tagged=True
                elif tag in activities_tags.keys(): 
                    event_activities_tags.append(tag)
                    tagged=True
                elif tag not in ignore_tags:
                    event_unknown_tags.append(tag)
                    unknown_tags[tag]=(dur,1) if tag not in unknown_tags.keys() else (unknown_tags[tag][0]+dur,unknown_tags[tag][1]+1)
                    tagged=True
            
            if tagged:
                #count the total tagged duration
                tagged_dur+=dur
                    
            # multi tags time assignement
            #  2 tags from same categories will split time equally between them
            #  2 tags from diferent categories will count total time 
            activities_dur = float(dur)/len(event_activities_tags) if len(event_activities_tags)>0 else 0
            for tag in event_activities_tags:
                activities_tags[tag]=(activities_tags[tag][0]+activities_dur,activities_tags[tag][1]+1)
            projects_dur = float(dur)/len(event_projects_tags) if len(event_projects_tags)>0 else 0
            for tag in event_projects_tags:
                projects_tags[tag]=(projects_tags[tag][0]+projects_dur,projects_tags[tag][1]+1)

            tags = u"|".join(event_projects_tags+event_activities_tags+event_unknown_tags)
            events.append([start_date.isoformat(), end_date.isoformat(), str(dur), exp, tags])

    events.sort()
    with codecs.open("%s_events_duration_tag.csv"%people["name"].replace(" ","_"),"w",encoding="utf-8") as event_file :
        event_file.write("beginning,end,duration(h),summary,tags\n")
        for l in events:
            event_file.write(u",".join(l)+"\n")


    #sort tags by hours duration
    projects_tags_hours_events_tuples=sorted(projects_tags.iteritems(), key=lambda i: i[1][0])
    projects_tags_hours_events_tuples.reverse()
    activities_tags_hours_events_tuples=sorted(activities_tags.iteritems(), key=lambda i: i[1][0])
    activities_tags_hours_events_tuples.reverse()
    unknown_tags_hours_events_tuples=sorted(unknown_tags.iteritems(), key=lambda i: i[1][0])
    unknown_tags_hours_events_tuples.reverse()

    total_duration_taged_projects = sum(_[1][0] for _ in projects_tags_hours_events_tuples)
    total_duration_taged_activities = sum(_[1][0] for _ in activities_tags_hours_events_tuples)
    total_duration_taged_unknown = sum(_[1][0] for _ in unknown_tags_hours_events_tuples)


    total_working_time = (date1 - date0).days/7.*36.5
    tag_coverage=100*tagged_dur/total_working_time
    print "tagged events represent %.2f"%(tag_coverage)
    all_tags[people["name"]]={u"tagged_coverage":tag_coverage}
    for _cat,_tags,_total_dur in ((u"projects",projects_tags_hours_events_tuples,total_duration_taged_projects),(u"activities",activities_tags_hours_events_tuples,total_duration_taged_activities),(u"unknown",unknown_tags_hours_events_tuples,total_duration_taged_unknown)):
        if len(_tags)>0:
            all_tags[people["name"]][_cat]=[]
        for (tag,(duration,nb_event)) in _tags:
            all_tags[people["name"]][_cat].append({u"tag":tag,u"duration":duration,u"duration_rate":100*duration/_total_dur,u"nb_event":nb_event})


json.dump(all_tags,codecs.open("tags_by_people.json","w",encoding="UTF8"),indent=4)

