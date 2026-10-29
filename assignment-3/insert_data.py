import ast
import io
import re
from pathlib import Path

import pandas as pd
from pymongo import ASCENDING, TEXT
from tabulate import tabulate

from DbConnector import DbConnector

DATA = Path("data/movies")
BATCH_SIZE = 50_000
GENDERS = {1: "female", 2: "male"}  # TMDB's codes, 0 is unknown


def read_metadata():
    """movies_metadata.csv, with lines that do not start a new record joined
    onto the line before. Three overviews hold an unquoted line break, which
    otherwise splits each of those movies over two broken rows.
    """
    text = (DATA / "movies_metadata.csv").read_text(encoding="utf-8")
    text = re.sub(r"\n(?!True,|False,)", " ", text)
    return pd.read_csv(io.StringIO(text), low_memory=False)


def parse(text):
    # The nested columns are Python literals (single quotes), not JSON.
    return ast.literal_eval(text) if isinstance(text, str) else []


def text_or_none(value):
    return value if isinstance(value, str) and value.strip() else None


def amount(value):
    """Budget and revenue in USD. 0 means unknown, and values under $1,000 are
    given in some other unit (often millions), so both become None.
    """
    return int(value) if pd.notna(value) and value >= 1000 else None


def movie_document(movie, credits, keywords):
    release_date = pd.to_datetime(movie.release_date, errors="coerce")
    collection = parse(movie.belongs_to_collection) or None
    cast = sorted(credits.get("cast", []), key=lambda person: person["order"])
    return {
        "_id": int(movie.id),
        "imdb_id": text_or_none(movie.imdb_id),
        "title": movie.title,
        "original_title": movie.original_title,
        "original_language": text_or_none(movie.original_language),
        "overview": text_or_none(movie.overview),
        "tagline": text_or_none(movie.tagline),
        "status": text_or_none(movie.status),
        "adult": movie.adult == "True",
        "release_date": None if pd.isna(release_date) else release_date.to_pydatetime(),
        "runtime": float(movie.runtime) if movie.runtime > 0 else None,
        "budget": amount(float(movie.budget)),
        "revenue": amount(movie.revenue),
        "popularity": float(movie.popularity),
        # TMDB shows 0 for a movie nobody has voted on.
        "vote_average": float(movie.vote_average) if movie.vote_count > 0 else None,
        "vote_count": int(movie.vote_count),
        "genres": [genre["name"] for genre in parse(movie.genres)],
        "production_companies": [c["name"] for c in parse(movie.production_companies)],
        "production_countries": [
            c["iso_3166_1"] for c in parse(movie.production_countries)
        ],
        "spoken_languages": [
            lang["iso_639_1"] for lang in parse(movie.spoken_languages)
        ],
        "collection": collection
        and {"id": collection["id"], "name": collection["name"]},
        "keywords": [keyword["name"] for keyword in keywords],
        "cast": [
            {
                "id": person["id"],
                "name": person["name"],
                "character": text_or_none(person["character"]),
                "gender": GENDERS.get(person["gender"]),
                "order": person["order"],
            }
            for person in cast
        ],
        "crew": [
            {
                "id": person["id"],
                "name": person["name"],
                "job": person["job"],
                "department": person["department"],
            }
            for person in credits.get("crew", [])
        ],
    }


def insert_movies(db):
    movies = read_metadata()
    # Two rows with the same id are the same movie, differing at most in
    # popularity and vote_count (by 1). Keep the one with the higher popularity.
    movies = movies.sort_values("popularity", ascending=False).drop_duplicates("id")
    credits = pd.read_csv(DATA / "credits.csv").drop_duplicates("id")
    keywords = pd.read_csv(DATA / "keywords.csv").drop_duplicates("id")
    credits_by_id = {
        movie_id: {"cast": parse(cast), "crew": parse(crew)}
        for movie_id, cast, crew in zip(credits["id"], credits["cast"], credits["crew"])
    }
    keywords_by_id = dict(zip(keywords["id"], keywords["keywords"].map(parse)))

    documents = [
        movie_document(
            movie, credits_by_id.get(movie.id, {}), keywords_by_id.get(movie.id, [])
        )
        for movie in movies.sort_values("id").itertuples(index=False)
    ]
    db.movies.insert_many(documents)
    db.movies.create_index([("overview", TEXT), ("tagline", TEXT)], name="text")
    return {int(movie_id) for movie_id in movies["id"]}


def insert_ratings(db, movie_ids):
    links = pd.read_csv(DATA / "links.csv").dropna(subset=["tmdbId"])
    to_tmdb = dict(zip(links["movieId"], links["tmdbId"].astype(int)))
    ratings = pd.read_csv(
        DATA / "ratings.csv",
        dtype={"userId": "int32", "movieId": "int32", "rating": "float32"},
    )
    ratings["movieId"] = ratings["movieId"].map(to_tmdb)
    ratings = ratings[ratings["movieId"].isin(movie_ids)]
    # Two MovieLens ids can link to the same TMDB movie. A user who rated both
    # keeps only the later rating.
    ratings = ratings.sort_values("timestamp").drop_duplicates(
        ["userId", "movieId"], keep="last"
    )
    ratings = ratings.sort_values(["userId", "movieId"])

    for start in range(0, len(ratings), BATCH_SIZE):
        batch = ratings.iloc[start : start + BATCH_SIZE]
        rated_at = pd.to_datetime(batch["timestamp"], unit="s").dt.to_pydatetime()
        db.ratings.insert_many(
            [
                {"user_id": user, "movie_id": movie, "rating": rating, "rated_at": when}
                for user, movie, rating, when in zip(
                    batch["userId"].tolist(),
                    batch["movieId"].astype(int).tolist(),
                    batch["rating"].tolist(),
                    rated_at,
                )
            ],
            ordered=False,
        )
        done = min(start + BATCH_SIZE, len(ratings))
        if done % 1_000_000 < BATCH_SIZE or done == len(ratings):
            print(f"{done:,} of {len(ratings):,} ratings inserted")
    db.ratings.create_index([("user_id", ASCENDING)])
    db.ratings.create_index([("movie_id", ASCENDING)])


def main():
    connection = DbConnector()
    db = connection.db
    for collection in ("movies", "ratings"):
        db.drop_collection(collection)

    movie_ids = insert_movies(db)
    print(f"{len(movie_ids):,} movies inserted")
    insert_ratings(db, movie_ids)

    counts = [
        (name, db[name].estimated_document_count()) for name in ("movies", "ratings")
    ]
    print(tabulate(counts, headers=["collection", "documents"], intfmt=","))
    connection.close_connection()


if __name__ == "__main__":
    main()
