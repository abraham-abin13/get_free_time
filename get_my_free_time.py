import argparse
import caldav
import os
import sys
import numpy as np
import pandas as pd
import datetime
from pathlib import Path

DATE = datetime.datetime.now().strftime('%Y-%m-%d')


# -----------
# CONFIG PARAMETERS
# -----------

USERNAME = '....'
PASSWORD = "...."
URL = "https://caldav.icloud.com" # if using ical
CALENDAR_NAMES = ['Work']  #add the names of calendars to use
NUM_WEEKS = 2
DAY_START_HOUR = datetime.time(hour=8, minute=0)
DAY_END_HOUR = datetime.time(hour=17, minute=0)


# -----------
# Classes & Functions
# -----------

def get_args(user_args, DAY_START_HOUR, DAY_END_HOUR):
    # if user does not provide args; will use default params defined at the top of the script

    # import pdb; pdb.set_trace()
    if (user_args.day_start_hour is False):
        day_start_hour = DAY_START_HOUR
    else:
        day_start_hour = datetime.time(hour=user_args.day_start_hour, minute=0)

    if (user_args.day_end_hour is False):
        day_end_hour = DAY_END_HOUR
    else:
        day_end_hour = datetime.time(hour=user_args.day_end_hour, minute=0)

    num_weeks = user_args.num_weeks

    return num_weeks, day_start_hour, day_end_hour


class freeTime(object):
    """docstring for FreeTime."""

    def __init__(self, query_start_date, query_end_date, url, username, password, calendar_name_list, day_start_hour, day_end_hour):
        super(freeTime, self).__init__()

        self.query_start_date = query_start_date
        self.query_end_date = query_end_date

        self.url = url
        self.username = username
        self.password = password

        self.calendar_name_list = calendar_name_list
        self.day_start_hour = day_start_hour
        self.day_end_hour = day_end_hour

        # get calendars
        client = caldav.DAVClient(
            url=self.url, username=self.username, password=self.password)
        my_principal = client.principal()
        self.calendars = my_principal.calendars()

        # make dictiionary with keys being individual days in the query date range
        this_day = self.query_start_date.date()
        events_per_day_dict, free_time_per_day_dict = {}, {}
        for dcount in range((self.query_end_date.date() - self.query_start_date.date()).days + 1):
            events_per_day_dict[this_day] = []
            free_time_per_day_dict[this_day] = []
            this_day = this_day + datetime.timedelta(days=1)

        self.free_time_per_day_dict = free_time_per_day_dict
        self.events_per_day_dict = events_per_day_dict

    def get_events(self):

        all_events = []
        for cal_name in self.calendar_name_list:

            cal_ind = np.where(
                [c.name == cal_name for c in self.calendars])[0][0]
            selected_cal = self.calendars[cal_ind]

            # get events
            events_fetched = selected_cal.date_search(
                start=self.query_start_date, end=self.query_end_date, expand=True)
            all_events.extend(events_fetched)

        self.all_events = all_events

    def get_busy_timeblocks(self):

        events_fetched = self.all_events

        for event in events_fetched:

            # get time start and end
            event_starttime = event.vobject_instance.vevent.dtstart.value.astimezone()
            event_endtime = event.vobject_instance.vevent.dtend.value.astimezone()
            timeblock = (event_starttime, event_endtime)

            # skip event if it does not have any hours associated witth it
            # these are likely day-long events
            if (hasattr(event_starttime, "hour") & hasattr(event_endtime, 'hour')):

                # add event to the day that the event starts
                event_starttime = event_starttime.date()
                self.events_per_day_dict[event_starttime].append(timeblock)

    def find_free_time(self):

        day_start = self.day_start_hour
        day_end = self.day_end_hour

        # create free time blocks
        for day, events in self.events_per_day_dict.items():

            hour_start = day_start

            # if no events; the entire day is availble!
            if (len(events) == 0):

                self.free_time_per_day_dict[day].append((day_start, day_end))
                continue

            for event in events:

                event_start_ = event[0]
                event_end_ = event[1]

                # if the event starts and ends outside of the hour_start and end
                if ((event_start_.time() <= day_start) & (event_end_.time() >= day_end)):
                    break  # no availability so exit loop

                # event ends even before the next free time block starts
                if event_end_.time() <= hour_start:
                    continue

                # if an event starts before or at the same time as when the next free block starts
                # then updated hour_start and go to next event
                if event_start_.time() <= hour_start:
                    # make the day start when this event ends
                    hour_start = event_end_.time()
                    continue

                # if the event_ends after the day_ends:  all the availability is used up!
                # stop the loop; don't even look at other events
                if event_end_.time() >= day_end:
                    self.free_time_per_day_dict[day].append(
                        (hour_start, event_start_))
                    break

                # if the event end occurs before the current hour-start (i.e. event already is within/subset of another event busy block )
                # skip to next iteration
                if event_end_.time() <= hour_start:
                    continue

                self.free_time_per_day_dict[day].append(
                    (hour_start, event_start_))

                # if event end time is after the day_end time
                if event_end_.time() >= day_end:
                    continue

                hour_start = event_end_.time()

            # after the very last event, append the final chunk of free time
            if event_end_.time() <= day_end:
                self.free_time_per_day_dict[day].append((hour_start, day_end))

    def print_available_times(self):

        # import pdb; pdb.set_trace()
        for day, events in self.free_time_per_day_dict.items():
            # if no events, do not print this day
            if len(events) == 0:
                continue

            day_str = f'({day.strftime("%a")}) {day.strftime("%b %d")},'

            all_free_slots = []
            for this_event in events:

                s_ = this_event[0].strftime("%-I:%M%p").replace(":00", '')
                e_ = this_event[1].strftime("%-I:%M%p").replace(":00", '')

                free_slot_string = f'{s_}-{e_}'.replace(
                    'AM', 'am').replace('PM', 'pm')
                all_free_slots.append(free_slot_string)

            final_free_slots_str = f"{day_str} {', '.join(all_free_slots)}"
            print(final_free_slots_str)

    def run(self):
        self.get_events()
        self.get_busy_timeblocks()
        self.find_free_time()

        self.print_available_times()



# %%
# -----------
# main
# -----------
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-n', '--num_weeks', action='store', type=int,
                        default=NUM_WEEKS,
                        dest='num_weeks',
                        help='number of weeks from today to provide free time')

    parser.add_argument('-s', '--day_start_hour', action='store', type=int,
                        default=False,
                        dest='day_start_hour',
                        help='At what hour do you want to *start* your day? Number between 0-23 (miliary time)')

    parser.add_argument('-e', '--day_end_hour', action='store', type=int,
                        default=False,
                        dest='day_end_hour',
                        help='At what hour do you want to *end* your day? Number between 0-23 (miliary time)')

    num_weeks, day_start_hour, day_end_hour = get_args(
        parser.parse_args(), DAY_START_HOUR, DAY_END_HOUR)

    # set up datetime format for query start and end dates
    query_start_date = datetime.datetime.now()
    query_end_date = query_start_date + datetime.timedelta(days=num_weeks * 7)

    freeTime = freeTime(query_start_date, query_end_date, URL, USERNAME,
                        PASSWORD, CALENDAR_NAMES, day_start_hour, day_end_hour)
    freeTime.run()
