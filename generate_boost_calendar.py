#!/usr/bin/env python
#
#	Print a year's worth of Boost release milestones as CSV, suitable for importing
#	into Google Calendar
#
#	Usage:
#		junk.py -y 2022 --release 82
#	means that 1.82.0 is the first release in 2020

import datetime
from optparse import OptionParser

# Subject,Start Date,Start Time,End Date,End Time,All Day Event,Description
# Boost 1.75.0 closed for new libraries and breaking changes,10/21/2020,12:00AM,10/21/2020,12:01AM,TRUE,Release branch is closed for new libraries and breaking changes to existing libraries. Still open for bug fixes and other routine changes to all libraries without release manager review.
# Boost 1.75.0 closed for major changes,10/28/2020,12:00AM,10/28/2020,12:01AM,TRUE,Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review.
# Boost 1.75.0 closed for beta,11/4/2020,12:00AM,11/4/2020,12:01AM,TRUE,"Release closed for all changes, except by permission of a release manager."
# Boost 1.75.0 beta,11/11/2020,12:00AM,11/11/2020,12:01AM,TRUE,Beta posted for download.
# Boost 1.75.0 open for bug fixes,11/12/2020,12:00AM,11/12/2020,12:01AM,TRUE,Release open for bug fixes and documentation updates. Other changes by permission of a release manager.
# Boost 1.75.0 closed,12/2/2020,12:00AM,12/2/2020,12:01AM,TRUE,"Release closed for all changes, except by permission of a release manager."
# Boost 1.75.0 release,12/9/2020,12:00AM,12/9/2020,12:01AM,TRUE,Release posted for download.

# Spring release on the second Wednesday of April.
# Summer release on the second Wednesday of August.
# Fall/Winter release on the second Wednesday of December.

skeleton = [
	[ 49, "Boost %s closed for new libraries and breaking changes", "12:00AM", "12:01AM", "TRUE", "Release branch is closed for new libraries and breaking changes to existing libraries. Still open for bug fixes and other routine changes to all libraries without release manager review." ],
	[ 42, "Boost %s closed for major changes",                      "12:00AM", "12:01AM", "TRUE", "Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review." ],
	[ 35, "Boost %s closed for beta",                               "12:00AM", "12:01AM", "TRUE", "Release closed for all changes, except by permission of a release manager." ],
	[ 28, "Boost %s beta",                                          "12:00AM", "12:01AM", "TRUE", "Beta posted for download." ],
	[ 27, "Boost %s open for bug fixes",                            "12:00AM", "12:01AM", "TRUE", "Release open for bug fixes and documentation updates. Other changes by permission of a release manager." ],
	[  7, "Boost %s closed",                                        "12:00AM", "12:01AM", "TRUE", "Release closed for all changes, except by permission of a release manager." ],
	[  0, "Boost %s release",                                       "12:00AM", "12:01AM", "TRUE", "Release posted for download." ]
]


def oneRelease(release, relDate):
	relStr = "1.%d.0" % release
	for s in skeleton:
		milestone = relDate - datetime.timedelta(days=s[0])
		mileStr = str(milestone)
		descStr = s[1] % relStr
		print("%s,%s,%s,%s,%s,%s,%s" % (descStr, mileStr, s[2], mileStr, s[3], s[4], s[5]))


# Based on https://stackoverflow.com/questions/28680896/how-can-i-get-the-3rd-friday-of-a-month-in-python/28681097
def second_wednesday(year, month):
    # The 8th is the lowest second day in the month
    second = datetime.date(year, month, 8)
    # What day of the week is the 8thth?
    w = second.weekday()
    # Wednesday is weekday 2
    if w != 2:
        # Replace just the day (of month)
        second = second.replace(day=(8 + (2 - w) % 7))
    return second


parser = OptionParser()

parser.add_option("-y", "--year",     default=None,   type="int",          dest="year",     help="year to generate CSV for")
parser.add_option("-r", "--release",  default=None,   type="int",          dest="release",  help="first release of the year")

(options, args) = parser.parse_args()

print ("Subject,Start Date,Start Time,End Date,End Time,All Day Event,Description")
oneRelease(options.release,     second_wednesday(options.year, 4))
oneRelease(options.release + 1, second_wednesday(options.year, 8))
oneRelease(options.release + 2, second_wednesday(options.year, 12))
