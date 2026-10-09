import sys
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import cast

from haversine import Unit, haversine
from tabulate import tabulate

from DbConnector import DbConnector

db = DbConnector()


def display(rows, headers, limit=20):
    print(tabulate(rows[:limit], headers=headers, floatfmt=".2f"))
    if len(rows) > limit:
        print(f"... {len(rows):,} rows in total")


def show(query, limit=20):
    db.cursor.execute(query)
    display(db.cursor.fetchall(), db.cursor.column_names, limit)


def task_1():
    """How many taxis, trips, and total GPS points are there?"""
    show("""
        SELECT (SELECT COUNT(*) FROM Taxi)  AS taxis,
               (SELECT COUNT(*) FROM Trip)  AS trips,
               (SELECT COUNT(*) FROM Point) AS points
    """)


def task_2():
    """What is the average number of trips per taxi?"""
    show("""
        SELECT COUNT(*) / (SELECT COUNT(*) FROM Taxi) AS avg_trips_per_taxi
        FROM Trip
    """)


def task_3():
    """List the top 20 taxis with the most trips."""
    show("""
        SELECT taxi_id, COUNT(*) AS trips
        FROM Trip
        GROUP BY taxi_id
        ORDER BY trips DESC
        LIMIT 20
    """)


def task_4():
    """a) What is the most used call type per taxi?
    b) For each call type, compute the average trip duration and distance,
    and also report the share of trips starting in four time bands: 00-06,
    06-12, 12-18, and 18-24.
    """
    db.cursor.execute("""
        SELECT taxi_id, call_type, COUNT(*)
        FROM Trip
        GROUP BY taxi_id, call_type
    """)
    counts = {}
    for taxi_id, call_type, trips in db.cursor.fetchall():
        counts.setdefault(taxi_id, {})[call_type] = trips
    rows = []
    for taxi_id, by_type in sorted(counts.items()):
        a, b, c = (by_type.get(call_type, 0) for call_type in "ABC")
        rows.append((taxi_id, a, b, c, max(by_type, key=by_type.get)))
    display(rows, ["taxi_id", "A", "B", "C", "most_used"])
    winners = Counter(row[-1] for row in rows)
    print("\nTaxis per most used call type:", dict(sorted(winners.items())))

    print()
    db.cursor.execute("""
        SELECT call_type, COUNT(*), AVG(duration_s) / 60, AVG(distance_m) / 1000
        FROM Trip
        WHERE n_points >= 3
        GROUP BY call_type
        ORDER BY call_type
    """)
    averages = cast(list[tuple[str, int, Decimal, float]], db.cursor.fetchall())
    db.cursor.execute("""
        SELECT call_type, HOUR(start_time) DIV 6 AS band, COUNT(*)
        FROM Trip
        WHERE n_points >= 3
        GROUP BY call_type, band
    """)
    bands = cast(list[tuple[str, int, int]], db.cursor.fetchall())
    per_band = {(call, band): trips for call, band, trips in bands}
    rows = []
    for call_type, trips, minutes, km in averages:
        shares = [100 * per_band.get((call_type, band), 0) / trips for band in range(4)]
        rows.append((call_type, trips, minutes, km, *shares))
    headers = ["call_type", "trips", "avg_minutes", "avg_km"]
    display(rows, headers + ["% 00-06", "% 06-12", "% 12-18", "% 18-24"])


def task_5():
    """Find the taxis with the most total hours driven as well as total
    distance driven. List them in order of total hours.
    """
    show("""
        SELECT taxi_id,
               SUM(duration_s) / 3600 AS hours,
               SUM(distance_m) / 1000 AS km
        FROM Trip
        GROUP BY taxi_id
        ORDER BY hours DESC
        LIMIT 20
    """)


def task_6():
    """Find the trips that passed within 100 m of Porto City Hall.
    (longitude, latitude) = (-8.62911, 41.15794)
    """
    city_hall = (41.15794, -8.62911)
    db.cursor.execute("""
        SELECT trip_id, latitude, longitude
        FROM Point
        WHERE latitude  BETWEEN 41.15794 - 0.0010 AND 41.15794 + 0.0010
          AND longitude BETWEEN -8.62911 - 0.0013 AND -8.62911 + 0.0013
        ORDER BY trip_id
    """)
    near = dict.fromkeys(
        trip_id
        for trip_id, lat, lon in db.cursor.fetchall()
        if haversine((lat, lon), city_hall, unit=Unit.METERS) <= 100
    )
    display([(trip_id,) for trip_id in near], ["trip_id"])


def task_7():
    """Identify the number of invalid trips. An invalid trip is defined as a
    trip with fewer than 3 GPS points.
    """
    show("""
        SELECT COUNT(*) AS invalid_trips
        FROM Trip
        WHERE n_points < 3
    """)


def task_8():
    """Find the trips that started on one calendar day and ended on the next
    (midnight crossers).
    """
    show("""
        SELECT trip_id, taxi_id, start_time,
               start_time + INTERVAL duration_s SECOND AS end_time
        FROM Trip
        WHERE DATE(start_time + INTERVAL duration_s SECOND) > DATE(start_time)
        ORDER BY start_time
    """)


def task_9():
    """Find the trips whose start and end points are within 50 m of each other
    (circular trips).
    """
    db.cursor.execute("""
        SELECT t.trip_id, t.n_points,
               a.latitude, a.longitude, b.latitude, b.longitude
        FROM Trip t
        JOIN Point a ON a.trip_id = t.trip_id AND a.seq = 0
        JOIN Point b ON b.trip_id = t.trip_id AND b.seq = t.n_points - 1
        WHERE t.n_points >= 3
    """)
    circular = []
    for trip_id, n_points, lat1, lon1, lat2, lon2 in db.cursor.fetchall():
        metres = haversine((lat1, lon1), (lat2, lon2), unit=Unit.METERS)
        if metres <= 50:
            circular.append((trip_id, n_points, metres))
    display(circular, ["trip_id", "n_points", "metres"])


def task_10():
    """For each taxi, compute the average idle time between consecutive trips.
    List the top 20 taxis with the highest average idle time.
    """
    db.cursor.execute("""
        SELECT taxi_id, start_time, duration_s
        FROM Trip
        ORDER BY taxi_id, start_time
    """)
    trips = cast(list[tuple[int, datetime, int]], db.cursor.fetchall())
    gaps = {}
    for (taxi_id, start, duration_s), (next_taxi, next_start, _) in pairwise(trips):
        if taxi_id == next_taxi:
            end = start + timedelta(seconds=duration_s)
            idle_s = (next_start - end).total_seconds()
            if idle_s >= 0:
                gaps.setdefault(taxi_id, []).append(idle_s)
    rows = [
        (taxi_id, sum(idle) / len(idle) / 3600, len(idle))
        for taxi_id, idle in gaps.items()
    ]
    rows.sort(key=lambda row: row[1], reverse=True)
    display(rows, ["taxi_id", "avg_idle_hours", "gaps"])


TASKS = [
    task_1,
    task_2,
    task_3,
    task_4,
    task_5,
    task_6,
    task_7,
    task_8,
    task_9,
    task_10,
]


def main():
    numbers = [int(arg) for arg in sys.argv[1:]] or range(1, len(TASKS) + 1)
    for number in numbers:
        task = TASKS[number - 1]
        print(f"\n===== Task {number} =====\n{task.__doc__}")
        task()
    db.close_connection()


if __name__ == "__main__":
    main()
