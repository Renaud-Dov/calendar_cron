# Calendar script


This script is a cron check for the calendar and send a discord notification if there is anything changed.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
ICS_URL="https://path/to/your/calendar.ics" \
WEBHOOK_URL="https://discord.com/api/webhooks/your/webhook" \
python app.py
```
