import sys
from collections import Counter
from statistics import median

from tabulate import tabulate

from DbConnector import DbConnector

connection = DbConnector()
movies = connection.db.movies
ratings = connection.db.ratings

YEAR = {"$year": "$release_date"}
DECADE = {"$subtract": [YEAR, {"$mod": [YEAR, 10]}]}


def display(rows, headers, limit=20):
    print(tabulate(rows[:limit], headers=headers, floatfmt=".2f"))
    if len(rows) > limit:
        print(f"... {len(rows):,} rows in total")


def show(pipeline, collection=movies, limit=20):
    documents = list(collection.aggregate(pipeline, allowDiskUse=True))
    headers = list(documents[0]) if documents else []
    display([list(document.values()) for document in documents], headers, limit)


def known(values):
    return [value for value in values if value is not None]


def task_1():
    """Considering only crew with job = Director, which 10 directors with >= 5
    movies have the highest median revenue? Also report each director's movie
    count and mean vote_average.
    """
    # Revenue is unknown for most movies, so the 5 movies must have a revenue.
    directors = movies.aggregate([
        {"$unwind": "$crew"},
        {"$match": {"crew.job": "Director"}},
        # A director listed twice for the same movie counts once.
        {"$group": {
            "_id": {"director": "$crew.id", "movie": "$_id"},
            "name": {"$first": "$crew.name"},
            "revenue": {"$first": "$revenue"},
            "vote_average": {"$first": "$vote_average"},
        }},
        {"$group": {
            "_id": "$_id.director",
            "name": {"$first": "$name"},
            "movies": {"$sum": 1},
            "revenues": {"$push": "$revenue"},
            "mean_vote": {"$avg": "$vote_average"},
        }},
        {"$project": {
            "name": 1, "movies": 1, "mean_vote": 1,
            "revenues": {"$filter": {"input": "$revenues", "cond": {"$ne": ["$$this", None]}}},
        }},
        {"$match": {"revenues.4": {"$exists": True}}},
    ])
    rows = [
        (d["name"], d["movies"], len(d["revenues"]), median(d["revenues"]) / 1e6, d["mean_vote"])
        for d in directors
    ]
    rows.sort(key=lambda row: row[3], reverse=True)
    display(rows, ["director", "movies", "with_revenue", "median_revenue_musd", "mean_vote"], 10)


def task_2():
    """List actor pairs that have co-starred in >= 3 movies together, their
    number of co-appearances, and their average movie vote_average. Sort by
    number of co-appearances.
    """
    show([
        # $setUnion drops an actor listed twice in the same movie.
        {"$project": {
            "vote_average": 1,
            "a": {"$setUnion": [{"$map": {"input": "$cast", "in": {"id": "$$this.id", "name": "$$this.name"}}}]},
        }},
        {"$set": {"b": "$a"}},
        {"$unwind": "$a"},
        {"$unwind": "$b"},
        {"$match": {"$expr": {"$lt": ["$a.id", "$b.id"]}}},
        {"$group": {
            "_id": {"a": "$a.id", "b": "$b.id"},
            "actor_1": {"$first": "$a.name"},
            "actor_2": {"$first": "$b.name"},
            "movies": {"$sum": 1},
            "mean_vote": {"$avg": "$vote_average"},
        }},
        {"$match": {"movies": {"$gte": 3}}},
        {"$sort": {"movies": -1, "mean_vote": -1}},
        {"$replaceWith": {
            "actor_1": "$actor_1", "actor_2": "$actor_2", "movies": "$movies", "mean_vote": "$mean_vote",
        }},
    ])


def task_3():
    """List the top 10 actors (with >= 10 credited movies) that have the widest
    genre breadth. Report the actor, the number of distinct genres they've
    appeared in, and up to 5 example genres.
    """
    show([
        {"$unwind": "$cast"},
        {"$group": {
            "_id": {"actor": "$cast.id", "movie": "$_id"},
            "name": {"$first": "$cast.name"},
            "genres": {"$first": "$genres"},
        }},
        {"$group": {
            "_id": "$_id.actor",
            "name": {"$first": "$name"},
            "movies": {"$sum": 1},
            "genres": {"$push": "$genres"},
        }},
        {"$match": {"movies": {"$gte": 10}}},
        {"$set": {"genres": {"$reduce": {
            "input": "$genres", "initialValue": [], "in": {"$setUnion": ["$$value", "$$this"]},
        }}}},
        {"$set": {"genre_count": {"$size": "$genres"}}},
        {"$sort": {"genre_count": -1, "movies": -1, "name": 1}},
        {"$limit": 10},
        {"$replaceWith": {
            "actor": "$name", "movies": "$movies", "genres": "$genre_count",
            "examples": {"$reduce": {
                "input": {"$slice": [{"$sortArray": {"input": "$genres", "sortBy": 1}}, 5]},
                "initialValue": "",
                "in": {"$concat": ["$$value", {"$cond": [{"$eq": ["$$value", ""]}, "", ", "]}, "$$this"]},
            }},
        }},
    ])


def task_4():
    """For film collections (belongs_to_collection.name not null) with >= 3
    movies, which 10 collections have the largest total revenue? For each,
    report movie count, total revenue, median vote_average, and the earliest ->
    latest release date.
    """
    collections = movies.aggregate([
        {"$match": {"collection.name": {"$ne": None}}},
        {"$group": {
            "_id": "$collection.id",
            "name": {"$first": "$collection.name"},
            "movies": {"$sum": 1},
            "with_revenue": {"$sum": {"$cond": [{"$ne": ["$revenue", None]}, 1, 0]}},
            "revenue": {"$sum": "$revenue"},
            "votes": {"$push": "$vote_average"},
            "first": {"$min": "$release_date"},
            "last": {"$max": "$release_date"},
        }},
        {"$match": {"movies": {"$gte": 3}}},
        {"$sort": {"revenue": -1}},
        {"$limit": 10},
    ])
    rows = [
        (
            c["name"], c["movies"], c["with_revenue"], c["revenue"] / 1e6,
            median(known(c["votes"])) if known(c["votes"]) else None,
            f"{c['first']:%Y-%m-%d} -> {c['last']:%Y-%m-%d}",
        )
        for c in collections
    ]
    headers = ["collection", "movies", "with_revenue", "revenue_musd", "median_vote", "released"]
    display(rows, headers, 10)


def task_5():
    """By decade (e.g., 1970s, 1980s, ...) and primary genre (first element in
    genres), what is the median runtime and movie count? List results sorted by
    decade then median runtime (desc).
    """
    groups = movies.aggregate([
        {"$match": {"release_date": {"$ne": None}, "runtime": {"$ne": None}, "genres.0": {"$exists": True}}},
        {"$group": {
            "_id": {"decade": DECADE, "genre": {"$first": "$genres"}},
            "runtimes": {"$push": "$runtime"},
        }},
    ])
    rows = [
        (f"{g['_id']['decade']}s", g["_id"]["genre"], median(g["runtimes"]), len(g["runtimes"]))
        for g in groups
    ]
    rows.sort(key=lambda row: (row[0], -row[2]))
    display(rows, ["decade", "primary_genre", "median_runtime", "movies"], len(rows))


def task_6():
    """For each movie's top-billed 5 cast (by order), what is the proportion of
    female cast? Aggregate by decade and list decades sorted by average female
    proportion (desc), including movie counts used. Unknown gender may be
    ignored.
    """
    show([
        {"$match": {"release_date": {"$ne": None}, "cast.0": {"$exists": True}}},
        {"$project": {
            "decade": DECADE,
            "genders": {"$filter": {
                "input": {"$slice": [{"$sortArray": {"input": "$cast", "sortBy": {"order": 1}}}, 5]},
                "cond": {"$ne": ["$$this.gender", None]},
            }},
        }},
        # A movie whose top 5 all have unknown gender is left out.
        {"$match": {"genders.0": {"$exists": True}}},
        {"$project": {
            "decade": 1,
            "female": {"$divide": [
                {"$size": {"$filter": {"input": "$genders", "cond": {"$eq": ["$$this.gender", "female"]}}}},
                {"$size": "$genders"},
            ]},
        }},
        {"$group": {"_id": "$decade", "female_share": {"$avg": "$female"}, "movies": {"$sum": 1}}},
        {"$sort": {"female_share": -1}},
        {"$replaceWith": {
            "decade": {"$concat": [{"$toString": "$_id"}, "s"]},
            "female_share": "$female_share",
            "movies": "$movies",
        }},
    ], limit=50)


def task_7():
    """Using a text search over overview and tagline, which 20 movies matching
    "noir" or "neo-noir" (and vote_count >= 50) have the highest vote_average?
    Return title, year, vote_average, and vote_count.
    """
    # The text index splits "neo-noir" into "neo" and "noir", so searching for
    # "noir" finds both. Searching for "neo-noir" would also match any "neo".
    show([
        {"$match": {"$text": {"$search": "noir"}, "vote_count": {"$gte": 50}}},
        {"$sort": {"vote_average": -1, "vote_count": -1}},
        {"$limit": 20},
        {"$replaceWith": {
            "title": "$title",
            "year": YEAR,
            "vote_average": "$vote_average",
            "vote_count": "$vote_count",
        }},
    ])


def task_8():
    """Which 20 director-actor pairs with >= 3 collaborations (same movie) have
    the highest mean vote_average, considering only movies with vote_count >=
    100? Include the pair's films count and mean revenue.
    """
    people = {"id": "$$this.id", "name": "$$this.name"}
    show([
        {"$match": {"vote_count": {"$gte": 100}}},
        {"$project": {
            "vote_average": 1,
            "revenue": 1,
            "director": {"$setUnion": [{"$map": {
                "input": {"$filter": {"input": "$crew", "cond": {"$eq": ["$$this.job", "Director"]}}},
                "in": people,
            }}]},
            "actor": {"$setUnion": [{"$map": {"input": "$cast", "in": people}}]},
        }},
        {"$unwind": "$director"},
        {"$unwind": "$actor"},
        # A director acting in their own movie is not a pair.
        {"$match": {"$expr": {"$ne": ["$director.id", "$actor.id"]}}},
        {"$group": {
            "_id": {"director": "$director.id", "actor": "$actor.id"},
            "director": {"$first": "$director.name"},
            "actor": {"$first": "$actor.name"},
            "films": {"$sum": 1},
            "mean_vote": {"$avg": "$vote_average"},
            "mean_revenue": {"$avg": "$revenue"},
        }},
        {"$match": {"films": {"$gte": 3}}},
        {"$sort": {"mean_vote": -1, "films": -1}},
        {"$limit": 20},
        {"$replaceWith": {
            "director": "$director",
            "actor": "$actor",
            "films": "$films",
            "mean_vote": "$mean_vote",
            "mean_revenue_musd": {"$divide": ["$mean_revenue", 1e6]},
        }},
    ])


def task_9():
    """Among movies where original_language != "en" but at least one production
    company or country is United States, which are the top 10 original
    languages by count? For each language, report the count and one example
    title.
    """
    # Companies have no country in the dataset, so a company counts when its
    # name says United States.
    show([
        {"$match": {
            "original_language": {"$nin": ["en", None]},
            "$or": [
                {"production_countries": "US"},
                {"production_companies": {"$regex": "United States"}},
            ],
        }},
        # The most popular movie of each language is its example.
        {"$sort": {"popularity": -1}},
        {"$group": {"_id": "$original_language", "movies": {"$sum": 1}, "example": {"$first": "$title"}}},
        {"$sort": {"movies": -1}},
        {"$limit": 10},
        {"$replaceWith": {"language": "$_id", "movies": "$movies", "example": "$example"}},
    ])


def task_10():
    """For each user, what is their ratings count, population variance of
    ratings, and number of distinct genres rated? List the top 10 most
    genre-diverse users, and separately the top 10 highest-variance users (only
    users with >= 20 ratings).
    """
    genres = {movie["_id"]: movie["genres"] for movie in movies.find({}, {"genres": 1})}
    users = ratings.aggregate([
        {"$group": {
            "_id": "$user_id",
            "ratings": {"$sum": 1},
            "std": {"$stdDevPop": "$rating"},
            "movies": {"$push": "$movie_id"},
        }},
        {"$match": {"ratings": {"$gte": 20}}},
    ], allowDiskUse=True)
    rows = []
    for user in users:
        rated = {genre for movie in user["movies"] for genre in genres[movie]}
        rows.append((user["_id"], user["ratings"], user["std"] ** 2, len(rated)))
    print(f"{len(rows):,} users with at least 20 ratings\n")
    headers = ["user_id", "ratings", "variance", "genres"]

    print("Most genre-diverse users (ties broken by most ratings):\n")
    rows.sort(key=lambda row: (row[3], row[1]), reverse=True)
    display(rows, headers, 10)
    widest = Counter(row[3] for row in rows)
    print(f"\n{widest[rows[0][3]]:,} users have rated all {rows[0][3]} genres")

    print("\nHighest-variance users:\n")
    rows.sort(key=lambda row: row[2], reverse=True)
    display(rows, headers, 10)


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
    connection.close_connection()


if __name__ == "__main__":
    main()
