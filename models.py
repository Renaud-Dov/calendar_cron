import datetime
import uuid
from typing import List, Optional

from sqlalchemy import Enum, ForeignKey, BigInteger, func, Column, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from engine import Base, engine


class Event(Base):
    __tablename__ = "events"

    uid: Mapped[str] = mapped_column(primary_key=True)
    group: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column(default=None)
    all_day: Mapped[bool] = mapped_column()
    begin: Mapped[datetime.datetime] = mapped_column()
    end: Mapped[datetime.datetime] = mapped_column()
    url: Mapped[Optional[str]] = mapped_column(default=None)
    location: Mapped[Optional[str]] = mapped_column(default=None)
