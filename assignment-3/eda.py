import ast
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from insert_data import read_metadata

DATA = Path("data/movies")
CACHE = Path("data/eda.pkl")
FIGURES = Path("report/figures")
FIGURES.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update(
    {"axes.grid": True, "grid.color": "#e4e3df", "axes.axisbelow": True}
)
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})

# The nested columns are Python literals (single quotes), not JSON.
NESTED = ["genres", "production_companies", "production_countries", "spoken_languages"]


def parse(text):
    if not isinstance(text, str):
        return None
    return ast.literal_eval(text)


def load():
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    movies = read_metadata()
    credits = pd.read_csv(DATA / "credits.csv")
    keywords = pd.read_csv(DATA / "keywords.csv")
    links = pd.read_csv(DATA / "links.csv")
    ratings = pd.read_csv(
        DATA / "ratings.csv",
        dtype={"userId": "int32", "movieId": "int32", "rating": "float32"},
    )
    for column in ("cast", "crew"):
        credits[column] = credits[column].map(parse)
    keywords["keywords"] = keywords["keywords"].map(parse)
    frames = movies, credits, keywords, links, ratings
    pd.to_pickle(frames, CACHE)
    return frames


def step(number, title):
    print(f"\n\n===== Step {number}: {title} =====\n")


step(1, "Understanding the problem and the data")
movies, credits, keywords, links, ratings = load()
files = {
    "movies_metadata.csv": movies,
    "credits.csv": credits,
    "keywords.csv": keywords,
    "links.csv": links,
    "ratings.csv": ratings,
}
print(pd.DataFrame({name: frame.shape for name, frame in files.items()},
                   index=["rows", "columns"]).T.to_string(), "\n")
print("The first movie:\n")
print(movies.iloc[0].to_string())
print("\nIts first cast and crew members:\n")
print(credits["cast"].iloc[0][0])
print(credits["crew"].iloc[0][0])

step(2, "Importing and inspecting the data")
raw = pd.read_csv(DATA / "movies_metadata.csv", low_memory=False)
malformed = ~raw["id"].astype(str).str.fullmatch(r"\d+")
print("Read as is, movies_metadata.csv has", len(raw), "rows, and in",
      malformed.sum(), "of them id is not a number:\n")
split = malformed | malformed.shift(-1, fill_value=False)
print(raw.loc[split, ["id", "title", "original_title", "release_date"]].to_string(), "\n")
print("An unquoted line break in the overview splits each of these movies in two.")
print("With such lines joined back up there are", len(movies), "rows, and every id")
print("and title is present:", movies["id"].notna().all() and movies["title"].notna().all(), "\n")
for column in ("budget", "popularity"):
    movies[column] = pd.to_numeric(movies[column])
for column in NESTED + ["belongs_to_collection"]:
    movies[column] = movies[column].map(parse)
movies["release_date"] = pd.to_datetime(movies["release_date"], errors="coerce")
print(pd.DataFrame({"type": movies.dtypes,
                    "distinct values": movies.astype(str).nunique()}).to_string())

step(3, "Handling missing data")
print("Missing values in movies_metadata.csv:\n")
print(movies.isna().sum()[lambda s: s > 0].to_string())
print("\nValues that are 0 but mean unknown:\n")
zeros = movies[["budget", "revenue", "runtime", "vote_count"]].eq(0).sum()
print(zeros.to_string())
print("\nEmpty lists:\n")
empty = {column: (~movies[column].astype(bool)).sum() for column in NESTED}
empty["cast"] = (credits["cast"].map(len) == 0).sum()
empty["crew"] = (credits["crew"].map(len) == 0).sum()
empty["keywords"] = (keywords["keywords"].map(len) == 0).sum()
print(pd.Series(empty).to_string())
print("\nlinks.csv rows without a tmdbId:", links["tmdbId"].isna().sum())
movie_ids = set(movies["id"])
print("Movies without a row in credits.csv: ", len(movie_ids - set(credits["id"])))
print("Movies without a row in keywords.csv:", len(movie_ids - set(keywords["id"])))
print("\nPlaceholders that also mean missing:\n")
overviews = movies["overview"].str.strip()
print(overviews[overviews.str.fullmatch(r"(?i)no overview( found)?\.?|")]
      .value_counts().rename("overviews").to_string())
print("imdb_id '0':", (movies["imdb_id"] == "0").sum())
cast_genders = pd.Series([p["gender"] for cast in credits["cast"] for p in cast])
print("\nCast gender codes (0 unknown, 1 female, 2 male):\n")
print(cast_genders.value_counts().sort_index().to_string())

step(4, "Exploring data characteristics")
known = movies[["budget", "revenue", "runtime", "vote_average", "vote_count"]]
known = known.mask(known[["budget", "revenue", "runtime"]].eq(0).reindex(
    columns=known.columns, fill_value=False))
known.loc[known["vote_count"] == 0, "vote_average"] = None
print("Numeric columns, 0 treated as unknown (vote_average without votes too):\n")
print(known.describe().round(1).to_string(), "\n")
print("skewness:\n" + known.skew().round(1).to_string(), "\n")
print(movies["status"].value_counts().to_string(), "\n")
print("Most common original languages:\n")
print(movies["original_language"].value_counts().head(8).to_string(), "\n")
genres = movies["genres"].explode().dropna().map(lambda g: g["name"])
print(f"{genres.nunique()} genres, most common:\n")
print(genres.value_counts().head(10).to_string(), "\n")
print("Ratings:\n")
print(ratings["rating"].value_counts().sort_index().to_string(), "\n")
per_user = ratings.groupby("userId").size()
print(f"{len(per_user):,} users, {ratings['movieId'].nunique():,} movies rated")
print("Ratings per user:\n")
print(per_user.describe().round(1).to_string())
titles = dict(zip(movies["id"], movies["title"]))
to_title = links.dropna().set_index("movieId")["tmdbId"].astype(int).map(titles)
most_rated = ratings["movieId"].value_counts().head(5)
print("\nMost rated movies:\n")
print(pd.DataFrame({"title": most_rated.index.map(to_title), "ratings": most_rated.values})
      .to_string(index=False))

step(5, "Performing data transformation")
movies["year"] = movies["release_date"].dt.year
movies["decade"] = (movies["year"] // 10 * 10).astype("Int64")
print("First release:", movies["release_date"].min().date())
print("Last release: ", movies["release_date"].max().date())
print("\nMovies per decade:\n")
print(movies["decade"].value_counts().sort_index().astype(int).to_string())
primary = movies["genres"].map(lambda g: g[0]["name"] if g else None)
print("\nMost common primary genre (first in genres):\n")
print(primary.value_counts().head(5).to_string())
rated = pd.to_datetime(ratings["timestamp"].agg(["min", "max"]), unit="s")
print("\nRatings from", rated["min"], "to", rated["max"])
spike = ratings["timestamp"].value_counts().head(1)
print(f"The most common timestamp, {pd.to_datetime(spike.index[0], unit='s')}, has "
      f"{spike.iloc[0]} ratings, likely a bulk import rather than real rating times")

step(6, "Visualizing relationships")
print("Correlation between the numeric columns (known values only):\n")
print(known.corr().round(2).to_string())
by_year = movies.groupby("year")["vote_average"].agg(["size", "median"])
print("\nMedian vote_average per decade:\n")
print(known.groupby(movies["decade"])["vote_average"].median().round(2).to_string())

fig, (per_year, stars) = plt.subplots(1, 2, figsize=(12, 4))
per_year.bar(by_year.index, by_year["size"], width=1, color=BLUE)
per_year.set(title="Movies per release year", xlabel="year", ylabel="movies")
counts = ratings["rating"].value_counts().sort_index()
stars.bar(counts.index, counts.values, width=0.4, color=BLUE)
stars.set(title="ratings.csv: ratings per star value", xlabel="rating",
          ylabel="ratings")
stars.yaxis.set_major_formatter("{x:,.0f}")
fig.savefig(FIGURES / "distributions.png", dpi=160, bbox_inches="tight")

step(7, "Handling outliers")
runtime = known["runtime"]
q1, q3 = runtime.quantile([0.25, 0.75])
upper = q3 + 1.5 * (q3 - q1)
print(f"IQR rule: a runtime above {upper:.0f} minutes is an outlier")
print("Outliers by that rule:", (runtime > upper).sum())
print(movies.nlargest(3, "runtime")[["title", "runtime"]].to_string(index=False))
print("\nBudgets or revenues under $1,000 (probably given in millions):")
tiny = movies[(movies["budget"].between(1, 999)) | (movies["revenue"].between(1, 999))]
print(len(tiny), "movies, for example:")
print(tiny[["title", "budget", "revenue"]].head(5).to_string(index=False))
print("\nMovies with votes but vote_average 0:",
      ((movies["vote_count"] > 0) & (movies["vote_average"] == 0)).sum())
print("Movies with no votes (vote_average is 0):", (movies["vote_count"] == 0).sum())

print("\nDuplicates:\n")
linked = links.dropna()
duplicates = {
    "repeated ids in movies_metadata.csv": movies["id"].duplicated().sum(),
    "  of which identical rows": movies.astype(str).duplicated().sum(),
    "repeated ids in credits.csv": credits["id"].duplicated().sum(),
    "repeated ids in keywords.csv": keywords["id"].duplicated().sum(),
    "repeated tmdbIds in links.csv": linked["tmdbId"].duplicated().sum(),
    "links to a tmdbId not in the metadata": (~linked["tmdbId"].isin(movie_ids)).sum(),
}
print(pd.Series(duplicates).to_string())
repeated = movies[movies["id"].duplicated(keep=False)].sort_values("id")
print()
print(repeated[["id", "title", "popularity", "vote_count"]].head(6).to_string(index=False))
differ = Counter(
    column
    for _, group in repeated.astype(str).groupby("id")
    for column in group.columns[group.nunique() > 1]
)
print("\nColumns that differ between rows with the same id:", dict(differ))
same_people = all(
    len({frozenset(p["id"] for p in cast) for cast in group["cast"]}) == 1
    and len({frozenset((p["id"], p["job"]) for p in crew) for crew in group["crew"]}) == 1
    for _, group in credits[credits["id"].duplicated(keep=False)].groupby("id")
)
print("Repeated ids in credits.csv list the same cast and crew:", same_people)
same_keywords = keywords.astype(str).duplicated().sum() == keywords["id"].duplicated().sum()
print("Repeated ids in keywords.csv are identical rows:", same_keywords)
print("\nA repeated title is not a duplicate. Different movies share titles:\n")
print(movies["title"].value_counts().head(3).to_string())
to_tmdb = dict(zip(linked["movieId"], linked["tmdbId"].astype(int)))
tmdb = ratings["movieId"].map(to_tmdb)
mapped = tmdb.isin(movie_ids)
print("\nRatings whose movie cannot be found:", (~mapped).sum())
print("  no tmdbId in links.csv:     ", tmdb.isna().sum())
print("  tmdbId not in the metadata: ", (tmdb.notna() & ~mapped).sum())
twice = pd.DataFrame({"user": ratings["userId"], "tmdb": tmdb})[mapped].duplicated()
print("Ratings repeated once mapped to tmdbId:", twice.sum())

step(8, "Communicating findings")
findings = {
    "movie rows, once split rows are joined": len(movies),
    "movies split over two rows": malformed.sum(),
    "repeated movie ids": movies["id"].duplicated().sum(),
    "movies without a release date": movies["release_date"].isna().sum(),
    "movies with unknown budget (0)": zeros["budget"],
    "movies with unknown revenue (0)": zeros["revenue"],
    "movies with budget or revenue under $1,000": len(tiny),
    "movies with no votes (vote_average 0)": (movies["vote_count"] == 0).sum(),
    "movies without genres": empty["genres"],
    "movies in a collection": movies["belongs_to_collection"].notna().sum(),
    "movies without cast": empty["cast"],
    "cast members with unknown gender": (cast_genders == 0).sum(),
    "ratings": len(ratings),
    "users": len(per_user),
    "ratings whose movie cannot be found": (~mapped).sum(),
    "ratings repeated once mapped to tmdbId": twice.sum(),
}
print(pd.Series(findings).map("{:,}".format).to_string())
