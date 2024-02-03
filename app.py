import datetime
from sys import stdout

import schedule

import discord
import ics
import requests
from functools import lru_cache
import time
from ics import Calendar
from sqlalchemy import select
from sqlalchemy.orm import Session

from engine import engine
from models import Event

import logging
import os


def check_env(env: str) -> str:
    value = os.environ.get(env)
    if not value:
        raise ValueError(f"{env} is not set")
    return value


URL = check_env("ICS_URL")
WEBHOOK_URL = check_env("WEBHOOK_URL")
DELAY = int(os.environ.get("DELAY", 5))

logs = logging.getLogger(__name__)
logs.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logs.addHandler(handler)


@lru_cache()
def get_ics(url, ttl_hash=None):
    del ttl_hash  # to emphasize we don't use it and to shut pylint up
    logs.info("Fetching ICS")
    r = requests.get(url)
    print("Initial encoding: ", r.encoding)
    r.encoding = "utf-8"
    return r.text


def get_ttl_hash(seconds=3600):
    """Return the same value withing `seconds` time period"""
    return round(time.time() / seconds)


def send_webhook_message(embed: discord.Embed):
    webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
    logs.debug("Sending webhook message")
    webhook.send(embed=embed)


def create_new_event(session: Session, event: ics.Event):
    event_model = Event(
        uid=str(event.uid),
        name=event.name,
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
    embed.add_field(name="Begin", value=event.begin.datetime.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="End", value=event.end.datetime.strftime("%Y-%m-%d %H:%M:%S"))
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
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt


def update_event(session: Session, event: ics.Event):
    logs.info(f"Ckecking event {event.name}")
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
        logs.info("Checking events")
        raw_ics = get_ics(URL, ttl_hash=get_ttl_hash())
        cal = Calendar(raw_ics)

        # print last 10 events from the calendar
        events = list(cal.events)
        # sort events by begin date
        events.sort(key=lambda e: e.begin.datetime)
        session = Session(engine)
        for event in events:
            update_event(session, event)

        # check if there are events to delete
        events_uid = [str(event.uid) for event in events]
        events_to_delete = list(session.execute(select(Event).where(Event.uid.notin_(events_uid))).scalars().all())
        delete_events(session, events_to_delete)
    except Exception as e:
        logs.error(f"An error occurred: {e}")


schedule.every(DELAY).minutes.do(main)
main()
while 1:
    schedule.run_pending()
    time.sleep(1)
