import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from haversine import Unit, haversine_vector
from matplotlib.collections import LineCollection

CSV = Path("data/porto/porto.csv")
CACHE = Path("data/eda.pkl")
FIGURES = Path("report/figures")
FIGURES.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update(
    {"axes.grid": True, "grid.color": "#e4e3df", "axes.axisbelow": True}
)
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})


def trip_stats(polyline):
    points = json.loads(polyline)
    if len(points) < 2:
        return len(points), 0.0, 0.0
    lat_lon = [(lat, lon) for lon, lat in points]
    steps = haversine_vector(lat_lon[:-1], lat_lon[1:], Unit.METERS)
    return len(points), steps.sum() / 1000, steps.max()


def load():
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    chunks = []
    for chunk in pd.read_csv(CSV, chunksize=100_000):
        stats = [trip_stats(polyline) for polyline in chunk.pop("POLYLINE")]
        columns = ["n_points", "km", "max_jump_m"]
        chunks.append(chunk.join(pd.DataFrame(stats, chunk.index, columns)))
    df = pd.concat(chunks)
    df.to_pickle(CACHE)
    return df


def step(number, title):
    print(f"\n\n===== Step {number}: {title} =====\n")


step(1, "Understanding the problem and the data")
first_row = pd.read_csv(CSV, nrows=1).iloc[0]
points = json.loads(first_row["POLYLINE"])
print(first_row.drop("POLYLINE").to_string())
print(f"POLYLINE        a list of {len(points)} [longitude, latitude] points:")
print(f"                {points[:3]} ...")

step(2, "Importing and inspecting the data")
df = load()
print("rows, columns:", df.shape, "\n")
print(pd.DataFrame({"type": df.dtypes, "distinct values": df.nunique()}).to_string())

step(3, "Handling missing data")
print("Missing values per column:\n")
print(df.isna().sum().to_string())
print("\nMissing origin values per call type:\n")
origin = df.groupby("CALL_TYPE")[["ORIGIN_CALL", "ORIGIN_STAND"]]
print(origin.agg(lambda column: column.isna().sum()).to_string())
print("\nTrips flagged MISSING_DATA:  ", df["MISSING_DATA"].sum())
print("Trips with an empty POLYLINE:", (df["n_points"] == 0).sum())

step(4, "Exploring data characteristics")
print(df["CALL_TYPE"].value_counts().to_string(), "\n")
print(df["DAY_TYPE"].value_counts().to_string(), "\n")
numbers = df[["n_points", "km"]]
print(numbers.describe().round(1).to_string(), "\n")
print("skewness:\n" + numbers.skew().round(1).to_string(), "\n")
print("Trips per taxi:\n")
print(df["TAXI_ID"].value_counts().describe().round(1).to_string())

step(5, "Performing data transformation")
df["start"] = pd.to_datetime(df["TIMESTAMP"], unit="s")
df["minutes"] = (df["n_points"] - 1).clip(lower=0) * 15 / 60
df["km_per_h"] = df["km"] / (df["minutes"] / 60)
print("First trip starts:", df["start"].min())
print("Last trip starts: ", df["start"].max())
print("Median trip lasts:", df["minutes"].median(), "minutes")
print("Median trip length:", round(df["km"].median(), 1), "km")
print("Median average speed:", round(df["km_per_h"].median(), 1), "km/h")

step(6, "Visualizing relationships")
by_hour = pd.crosstab(df["start"].dt.hour, df["CALL_TYPE"])
print("Busiest starting hour (UTC) per call type:\n")
print(by_hour.idxmax().to_string())
print("\nMedian minutes per call type:\n")
print(df.groupby("CALL_TYPE")["minutes"].median().to_string())
print("\nCorrelation between the numeric columns:\n")
print(df[["n_points", "km", "max_jump_m"]].corr().round(2).to_string())

polylines = pd.read_csv(CSV, nrows=300_000)["POLYLINE"].map(json.loads)
trips = [points for points in polylines if len(points) >= 2]
fig, (wide, porto) = plt.subplots(1, 2, figsize=(12, 5))
for ax, alpha in ((wide, 0.8), (porto, 0.3)):
    ax.add_collection(LineCollection(trips, color=BLUE, linewidth=0.5, alpha=alpha))
    ax.autoscale()
    ax.set(xlabel="longitude", ylabel="latitude")
wide.set_title("The first 300,000 trips, all points")
porto.set_title("The same trips, zoomed in on Porto")
porto.set(xlim=(-8.70, -8.55), ylim=(41.11, 41.22))
fig.savefig(FIGURES / "trajectories.png", dpi=160, bbox_inches="tight")

step(7, "Handling outliers")
q1, q3 = df["n_points"].quantile([0.25, 0.75])
upper = q3 + 1.5 * (q3 - q1)
too_long = df["n_points"] > upper
too_short = df["n_points"] < 3
repeated = df["TRIP_ID"].duplicated(keep=False)
gps_jump = df["max_jump_m"] > 1000
print(f"IQR rule: a trip with more than {upper:.0f} points is an outlier")
print("Outliers by that rule:     ", too_long.sum())
print("Longest trip (hours):      ", round(df["minutes"].max() / 60, 1))
print("Longest trip (km):         ", round(df["km"].max(), 1))
print("Trips with under 3 points: ", too_short.sum())
print("Trips with a jump > 1 km:  ", gps_jump.sum())
jump_share = df.loc[gps_jump, "km"].sum() / df["km"].sum()
print("  their share of all km:   ", f"{jump_share:.1%}")
print("Rows sharing a TRIP_ID:    ", repeated.sum())
built = df["TIMESTAMP"].astype(str) + "6" + df["TAXI_ID"].astype(str)
same = (built == df["TRIP_ID"].astype(str)).mean()
print(f"TRIP_ID = TIMESTAMP + '6' + TAXI_ID in {same:.0%} of rows\n")
columns = ["TRIP_ID", "CALL_TYPE", "n_points"]
print(df.loc[repeated, columns].sort_values(columns).head(6).to_string(index=False))

fig, ax = plt.subplots(figsize=(8, 4))
points = df["n_points"].clip(upper=200)
ax.hist(points[~too_short], bins=range(202), color=BLUE, label="trips")
ax.hist(points[too_short], bins=range(202), color=ORANGE, label="under 3 points")
fence = f"IQR fence ({upper:.0f} points)"
ax.axvline(upper, color="black", linestyle="--", linewidth=1, label=fence)
ax.set(title="GPS points per trip (200 = 200 or more)", xlabel="points", ylabel="trips")
ax.yaxis.set_major_formatter("{x:,.0f}")
ax.legend(frameon=False)
fig.savefig(FIGURES / "points_per_trip.png", dpi=160, bbox_inches="tight")

step(8, "Communicating findings")
findings = {
    "rows (trips) in the file": len(df),
    "GPS points in total": df["n_points"].sum(),
    "taxis": df["TAXI_ID"].nunique(),
    "type B trips without a stand": (
        (df["CALL_TYPE"] == "B") & df["ORIGIN_STAND"].isna()
    ).sum(),
    "trips flagged MISSING_DATA": df["MISSING_DATA"].sum(),
    "trips with an empty POLYLINE": (df["n_points"] == 0).sum(),
    "trips with under 3 points": too_short.sum(),
    "outlier long trips (IQR rule)": too_long.sum(),
    "trips with a GPS jump > 1 km": gps_jump.sum(),
    "extra rows from repeated TRIP_IDs": df["TRIP_ID"].duplicated().sum(),
    "distinct DAY_TYPE values": df["DAY_TYPE"].nunique(),
}
print(pd.Series(findings).map("{:,}".format).to_string())
