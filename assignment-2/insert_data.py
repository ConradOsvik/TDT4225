import json
import tempfile
from pathlib import Path

import pandas as pd
from haversine import Unit, haversine_vector
from tabulate import tabulate

from DbConnector import DbConnector

CSV = Path("data/porto/porto.csv")
CHUNK_SIZE = 50_000

CREATE_TABLES = [
    """
    CREATE TABLE Taxi (
        taxi_id INT NOT NULL PRIMARY KEY
    )
    """,
    """
    CREATE TABLE Trip (
        trip_id      BIGINT   NOT NULL PRIMARY KEY,
        taxi_id      INT      NOT NULL,
        call_type    CHAR(1)  NOT NULL,  -- A dispatched, B taxi stand, C street
        origin_call  INT      NULL,      -- customer id, only for call type A
        origin_stand INT      NULL,      -- taxi stand id, only for call type B
        start_time   DATETIME NOT NULL,  -- UTC
        n_points     INT      NOT NULL,  -- GPS points in the trip
        duration_s   INT      NOT NULL,  -- (n_points - 1) * 15 seconds
        distance_m   DOUBLE   NOT NULL,  -- sum of haversine distances between points
        FOREIGN KEY (taxi_id) REFERENCES Taxi (taxi_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE Point (
        trip_id   BIGINT            NOT NULL,
        seq       SMALLINT UNSIGNED NOT NULL,  -- position in the trip, from 0
        longitude DOUBLE            NOT NULL,
        latitude  DOUBLE            NOT NULL,
        PRIMARY KEY (trip_id, seq),
        FOREIGN KEY (trip_id) REFERENCES Trip (trip_id) ON DELETE CASCADE
    )
    """,
]

LOAD_FILE = (
    "LOAD DATA LOCAL INFILE '{file}' INTO TABLE {table} FIELDS TERMINATED BY ','"
)


def count_points(polyline):
    return 0 if polyline == "[]" else polyline.count("],[") + 1


def trip_distance(points):
    if len(points) < 2:
        return 0.0
    lat_lon = [(lat, lon) for lon, lat in points]
    return float(haversine_vector(lat_lon[:-1], lat_lon[1:], Unit.METERS).sum())


def create_tables(db):
    for table in ("Point", "Trip", "Taxi"):
        db.cursor.execute(f"DROP TABLE IF EXISTS {table}")
    for statement in CREATE_TABLES:
        db.cursor.execute(statement)


def insert_trips(db, trips, folder):
    trip_file, point_file = folder / "trips.csv", folder / "points.csv"

    polylines = [json.loads(text) for text in trips["POLYLINE"]]

    rows = pd.DataFrame(
        {
            "trip_id": trips["TRIP_ID"],
            "taxi_id": trips["TAXI_ID"],
            "call_type": trips["CALL_TYPE"],
            "origin_call": trips["ORIGIN_CALL"].astype("Int64"),
            "origin_stand": trips["ORIGIN_STAND"].astype("Int64"),
            "start_time": pd.to_datetime(trips["TIMESTAMP"], unit="s"),
            "n_points": [len(points) for points in polylines],
            "duration_s": [max(len(points) - 1, 0) * 15 for points in polylines],
            "distance_m": [trip_distance(points) for points in polylines],
        }
    )
    rows.to_csv(trip_file, header=False, index=False, na_rep="\\N")

    with open(point_file, "w") as file:
        for trip_id, points in zip(trips["TRIP_ID"], polylines):
            file.writelines(
                f"{trip_id},{seq},{lon},{lat}\n"
                for seq, (lon, lat) in enumerate(points)
            )

    db.cursor.execute(LOAD_FILE.format(file=trip_file, table="Trip"))
    db.cursor.execute(LOAD_FILE.format(file=point_file, table="Point"))
    db.db_connection.commit()


def main():
    db = DbConnector()
    create_tables(db)

    ids = pd.read_csv(CSV, usecols=["TRIP_ID", "TAXI_ID"])
    repeated_ids = set(ids.loc[ids["TRIP_ID"].duplicated(), "TRIP_ID"])
    taxis = [(int(taxi_id),) for taxi_id in ids["TAXI_ID"].unique()]
    db.cursor.executemany("INSERT INTO Taxi (taxi_id) VALUES (%s)", taxis)
    db.db_connection.commit()

    best = {}
    done = 0
    with tempfile.TemporaryDirectory() as folder:
        for chunk in pd.read_csv(CSV, chunksize=CHUNK_SIZE):
            chunk = chunk[~chunk["MISSING_DATA"]]

            repeated = chunk["TRIP_ID"].isin(repeated_ids)
            for row in chunk[repeated].itertuples(index=False):
                kept = best.get(row.TRIP_ID)
                if kept is None or count_points(row.POLYLINE) > count_points(
                    kept.POLYLINE
                ):
                    best[row.TRIP_ID] = row

            insert_trips(db, chunk[~repeated], Path(folder))
            done += len(chunk)
            print(f"{done:,} rows of the CSV processed")

        insert_trips(db, pd.DataFrame(list(best.values())), Path(folder))

    counts = []
    for table in ("Taxi", "Trip", "Point"):
        db.cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts.append((table, db.cursor.fetchall()[0][0]))
    print(tabulate(counts, headers=["table", "rows"], intfmt=","))
    db.close_connection()


if __name__ == "__main__":
    main()
