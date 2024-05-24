create table public.events
(
    uid         varchar   not null
        primary key,
    name        varchar   not null,
    description varchar,
    all_day     boolean   not null,
    begin       timestamp not null,
    "end"       timestamp not null,
    url         varchar,
    location    varchar,
    "group"     varchar
);
