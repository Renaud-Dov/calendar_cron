import datetime
from sys import stdout


import discord
import ics
import requests
from ics import Calendar
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from engine import engine
from models import Event

import logging
import os
import re


def check_env(env: str) -> str:
    value = os.environ.get(env)
    if not value:
        raise ValueError(f"{env} is not set")
    return value


URL = check_env("ICS_URL")
GROUP = check_env("GROUP")
WEBHOOK_URLS = check_env("WEBHOOK_URLS").split(",")
FILTER_REGEX = os.environ.get("FILTER_REGEX", None)

# add stack trace to logs if error
logs = logging.getLogger(__name__)
logs.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logs.addHandler(handler)


def get_ics(url):
    logs.info("Fetching ICS")
    r = requests.get(url)
    logs.debug("Initial encoding: ", r.encoding)
    r.encoding = "utf-8"
    return r.text

def send_webhook_message(embed: discord.Embed):
    for WEBHOOK_URL in WEBHOOK_URLS:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
        logs.debug("Sending webhook message")
        webhook.send(embed=embed)


def datetime_to_timestamp(dt: datetime.datetime) -> str:
    return "<t:{}:f>".format(int(dt.timestamp()))


def create_new_event(session: Session, event: ics.Event):
    event_model = Event(
        uid=str(event.uid),
        name=event.name,
        group=GROUP,
        description=event.description,
        all_day=event.all_day,
        begin=event.begin.datetime,
        end=event.end.datetime,
        url=event.url,
        location=event.location
    )
    session.add(event_model)
    session.commit()
    logs.info(f"Event {event.name} has been added")

    embed = discord.Embed(title="New event", description=f"Event {event.name} has been added",
                          color=discord.Color.green())
    embed.add_field(name="Description", value=event.description)
    embed.add_field(name="All day", value=event.all_day)
    embed.add_field(name="Begin", value=datetime_to_timestamp(event.begin.datetime))
    embed.add_field(name="End", value=datetime_to_timestamp(event.end.datetime))
    embed.add_field(name="URL", value=event.url)
    embed.add_field(name="Location", value=event.location)

    send_webhook_message(embed)


def get_diff(event: ics.Event, event_model: Event):
    diff = {}
    if event.name != event_model.name:
        diff["name"] = (event_model.name, event.name)
    if event.description != event_model.description:
        diff["description"] = (event_model.description, event.description)
    if event.all_day != event_model.all_day:
        diff["all_day"] = (event_model.all_day, event.all_day)
    if str_datetime(event.begin.datetime) != str_datetime(event_model.begin):
        diff["begin"] = (event_model.begin, event.begin.datetime)
    if str_datetime(event.end.datetime) != str_datetime(event_model.end):
        diff["end"] = (event_model.end, event.end.datetime)
    if event.url != event_model.url:
        diff["url"] = (event_model.url, event.url)
    if event.location != event_model.location:
        diff["location"] = (event_model.location, event.location)
    return diff


def str_datetime(dt: str | datetime.datetime) -> str:
    if isinstance(dt, datetime.datetime):
        return datetime_to_timestamp(dt)
    return dt


def update_event(session: Session, event: ics.Event):
    logs.debug(f"Checking event {event.name}")
    event_model = session.execute(select(Event).where(Event.uid == str(event.uid))).scalar_one_or_none()
    if not event_model:
        create_new_event(session, event)
    else:
        diff: dict[str, tuple[object, object] | object] = get_diff(event, event_model)
        if diff:
            event_model.name = event.name
            event_model.description = event.description
            event_model.all_day = event.all_day
            event_model.begin = event.begin.datetime
            event_model.end = event.end.datetime
            event_model.url = event.url
            event_model.location = event.location
            session.commit()
            logs.info(f"Event {event.name} has been updated")
            embed = discord.Embed(title="Event updated", description=f"Event {event.name} has been updated",
                                  color=discord.Color.orange(), timestamp=event.begin.datetime)

            for key, value in diff.items():
                key = key.capitalize()
                if isinstance(value, tuple):
                    value_from, value_to = value
                    embed.add_field(name=key, value=f"{str_datetime(value_from)} -> {str_datetime(value_to)}")
                else:
                    embed.add_field(name=key, value=str(value))
            send_webhook_message(embed)


def delete_events(session: Session, events_to_delete: list[Event]):
    # sort events by begin date
    events_to_delete.sort(key=lambda e: e.begin)
    for event in events_to_delete:
        embed = discord.Embed(title="Event deleted", description=f"Event {event.name} has been deleted",
                              color=discord.Color.red(), timestamp=event.begin)
        logs.info(f"Event {event.name} has been deleted")
        session.delete(event)
        session.commit()
        send_webhook_message(embed)


def main():
    try:
        logs.info(f"Checking events for group {GROUP}")
        raw_ics = get_ics(URL)
        cal = Calendar(raw_ics)
        logs.info("Events fetched")

        # print last 10 events from the calendar
        events = list(cal.events)
        # sort events by begin date
        events.sort(key=lambda e: e.begin.datetime)
        if FILTER_REGEX:
            events = [event for event in events if re.match(FILTER_REGEX, event.name)]
        if len(events) == 0:
            logs.info("No events found")
            return
        session = Session(engine)
        for event in events:
            update_event(session, event)

        # check if there are events to delete
        events_uid = [str(event.uid) for event in events]
        events_to_delete = list(session.execute(
            select(Event).where(
                and_(
                    Event.group == GROUP,
                    Event.uid.notin_(events_uid)
                )
            )).scalars().all())
        delete_events(session, events_to_delete)
        logs.info("Events checked")
    except Exception as e:
        logs.error(f"An error occurred: {e}")
        # show stack trace in logs
        logs.exception(e)


main()
