#let title = "Report"
#let group = "111"
#let students = "Conrad Osvik, Jakob Huuse"
#let show-notes = true

#let grey-rule = line(length: 100%, stroke: 1pt + rgb("#a0a0a0"))

#set document(title: "TDT4225 Assignment 3 report", author: students)
#set page(
  paper: "a4",
  margin: (x: 2.54cm, top: 2.95cm, bottom: 2.54cm),
  header-ascent: 0.3cm,
  header: stack(
    spacing: 0.75cm,
    grid(
      columns: (1fr, 1fr),
      align: (left + horizon, right + horizon),
      image("ntnu-logo.png", width: 3.86cm), text(fill: rgb("#999999"))[TDT4225],
    ),
    grey-rule,
  ),
  footer-descent: 0.65cm,
  footer: stack(
    spacing: 0.3cm,
    grey-rule,
    align(center, context counter(page).display()),
  ),
)
#set text(font: "Lato", size: 12pt, lang: "en")
#set par(leading: 0.66em, spacing: 1.2em)
#show heading: set text(size: 12pt)
#show heading: set block(above: 1.8em, below: 0.7em)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 3): set text(style: "italic")
#show <ai-use>: set text(size: 12pt)
#show raw.where(block: true): set text(size: 9pt)
#show raw.where(block: false): set text(size: 10.5pt)
#show figure.caption: set text(size: 10pt)
#set table(inset: 5pt, stroke: 0.5pt + rgb("#a0a0a0"))

#let notes(body) = if show-notes {
  block(
    width: 100%,
    inset: (left: 10pt, y: 6pt),
    stroke: (left: 2pt + rgb("#eb6834")),
    text(size: 10pt, fill: rgb("#444444"), body),
  )
}
#let prompt(body) = block(inset: (left: 8pt), emph(body))
// Boxes taller than about a page (task 5) may break across pages.
#let terminal(output) = block(
  width: 100%,
  breakable: output.split("\n").len() > 60,
  fill: rgb("#f4f4f2"),
  stroke: 0.5pt + rgb("#d0d0cc"),
  inset: 7pt,
  radius: 2pt,
  {
    show raw: set text(size: 7.5pt)
    raw(output.trim(), block: true)
  },
)
#let eda-step(n) = {
  let output = read("results/eda.txt").split("===== Step ")
  terminal("===== Step " + output.at(n))
}
#let task-output(n) = {
  let output = read("results/task" + str(n) + ".txt")
  let start = output.position("===== Task")
  let body = output.slice(start).split("Connection to").at(0)
  terminal(body.trim().trim("-", at: end))
}

#v(0.6em)
#align(center)[
  #text(size: 18pt, weight: "bold", title) \
  #text(size: 14pt)[Assignment 3 - MongoDB]
]
#v(0.6em)
*Group*: #group \
*Students*: #students
#v(0.6em)

= Introduction

The task is about analysing The Movies Dataset from Kaggle, which holds metadata for about 45,000 movies along with their cast, crew and keywords, and 26 million ratings from 270,000 MovieLens users. Many of the fields are nested lists and objects, which fits a document database well. The first part of this task is to perform EDA on the dataset, clean it, and insert it into a MongoDB database. The second part is about performing queries on the dataset and reporting the findings.

This assignment was worked on by the two of us. We worked on all parts of the assignment together, from the EDA and cleaning to the schema, insertion and queries. We used MongoDB 7.0.1 in Docker on a MacBook Pro instead of the VM. For coding we used Python 3.13 with uv and PyMongo 4.10.1, and pandas and matplotlib for the EDA.

We run three scripts in order, first `eda.py`, then `insert_data.py`, and lastly `queries.py`.

Git was used for this project and the repo url is: https://github.com/ConradOsvik/TDT4225/tree/main/assignment-3

= Results

== Part 1: Exploratory data analysis

`eda.py` goes through eight steps, from understanding the data to communicating the findings, and its full output is in the appendix. All five files are loaded with pandas, and the nested columns are parsed once and cached, so later runs take about 15 seconds.

=== Overview of the data

The dataset consists of five files that we use. `movies_metadata.csv` has one row per movie with 24 columns, `credits.csv` has the cast and crew of each movie, `keywords.csv` has plot keywords, `ratings.csv` has 26,024,289 ratings and `links.csv` maps between the ids of the two sources. The movies come from TMDB and are identified by TMDB ids, while the ratings come from MovieLens and use MovieLens ids, so `links.csv` is needed to connect a rating to a movie.

The nested columns like `genres`, `cast` and `belongs_to_collection` look like JSON, but they are Python literals with single quotes, so `json.loads` can't read them and we parse them with `ast.literal_eval`. There are 20 genres, with Drama, Comedy and Thriller being the most common, and 71% of the movies are in English. The movies span from 1874 to 2020, but most are from after 1990. The ratings go from 0.5 to 5 in half steps, 4.0 being the most common, and a median user has 30 ratings while the most active has 18,276. Budget, revenue and vote count are heavily right skewed, so we use medians where it matters.

#figure(
  image("figures/distributions.png", width: 100%),
  caption: [Left: movies per release year. Right: how often each rating value
    is given in `ratings.csv`.],
) <fig-distributions>

=== Problems found

The biggest problem was that `movies_metadata.csv` can't be read correctly as is. Three movies have an unquoted line break in their overview, which makes pandas split each of them into two rows. The first row stops halfway through the overview, and in the second row every value is shifted, so the id column holds a date and `popularity` holds a tagline. This is also why `budget` and `popularity` are read as text instead of numbers.

Many values are 0 when they are actually unknown. 36,573 movies have a budget of 0 and 38,055 a revenue of 0, which is most of the dataset, and 1,558 have a runtime of 0. 2,899 movies have no votes, and TMDB shows their `vote_average` as 0, which is not the same as a rating of 0. 356 movies have a budget or revenue under \$1,000, like a revenue of \$1, which is most likely in millions or just wrong. There are also placeholders like "No overview found." for 133 overviews.

There are duplicates in several files. 30 movie ids appear twice in the metadata, where 17 are identical rows and in the rest only `popularity` differs, and twice `vote_count` by 1. `credits.csv` repeats 44 ids and `keywords.csv` 987, and when we checked them they list the same people and keywords. A repeated title is not a duplicate though, there are 11 different movies called Cinderella.

For the ratings, 42,707 can't be connected to a movie. 13,503 of them have a MovieLens id without a TMDB id in `links.csv`, and 29,204 link to a TMDB id that isn't in the metadata. 30 TMDB ids are linked from two MovieLens ids, which gives 125 cases of a user rating the same movie twice. 40% of the cast also has unknown gender.

#eda-step(8)

=== Cleaning decisions

The three split movies are repaired instead of removed. Every real row starts with the `adult` column, which is `True` or `False`, so a line that starts with anything else is joined back onto the line before it. After this all 45,463 rows have a numeric id and a title.

For the repeated movie ids we keep one row per id, as they are the same movie. The data has no date telling which copy is newer, so we keep the one with the highest popularity, and since only popularity differs it does not matter much. Repeated ids in `credits.csv` and `keywords.csv` are dropped as they hold the same data. This has to be done before joining them with the metadata, otherwise a movie is counted twice in every query.

Budgets, revenues and runtimes of 0, and budgets and revenues under \$1,000, are stored as `null`, and so is `vote_average` for movies without votes. MongoDB's `$avg` and `$sum` skip `null`, so these don't pull the averages and medians down. If we kept the zeros, the median revenue for almost every director in task 1 would be 0. Movies with missing genres, cast or release date are kept, and are left out only in the tasks that need those fields. The long runtimes are kept as well, as most of them are real miniseries like Centennial at 1,256 minutes.

For the ratings, the MovieLens id is replaced with the TMDB id when inserting, and the 42,707 ratings that can't be connected to a movie are dropped, which is 0.16%. When a user has rated the same movie twice we keep the latest rating. Dates and timestamps are stored as MongoDB dates, and the nested columns are reduced to the parts the tasks use.

The result is 45,433 movies and 25,981,457 ratings.

== Part 1: Schema and insertion

We went with two collections, `movies` and `ratings`. Coming from MySQL, the obvious design would be a table each for movies, genres, people, cast, crew, keywords, companies and so on. In MongoDB most of this can be embedded in the movie document instead, since it is always read together with the movie, a movie only has a limited number of each, and they don't change. This way a movie document works like a movie page on IMDb, with everything about the movie in one read and no joins.

The ratings are the exception. A movie can have up to 91,921 ratings (Forrest Gump), the number grows over time, and task 10 looks at the ratings per user rather than per movie. Embedding them in the movies would make the documents several MB each and task 10 would have to unwind every movie. So the ratings have their own collection, referencing the movie by its TMDB id, which is the `_id` of the movie. There is no users collection as we know nothing about a user except their id.

#let entity(name, ..columns) = table(
  columns: 1,
  align: left,
  fill: (_, row) => if row == 0 { rgb("#e8eef8") },
  table.header(strong(name)),
  ..columns.pos().map(column => text(size: 9pt, raw(column))),
)
#figure(
  grid(
    columns: 3,
    align: horizon,
    column-gutter: 8pt,
    entity(
      "movies",
      "_id               TMDB id",
      "title, original_title",
      "overview, tagline (text index)",
      "release_date      date",
      "runtime, budget, revenue",
      "vote_average, vote_count",
      "genres            [string]",
      "keywords          [string]",
      "production_companies, …",
      "collection        {id, name}",
      "cast  [{id, name, gender, …}]",
      "crew  [{id, name, job, …}]",
    ),
    [1 #sym.arrow.r N],
    entity("ratings", "_id         ObjectId", "user_id     (index)", "movie_id    → movies._id", "rating", "rated_at    date"),
  ),
  kind: image,
  caption: [The two collections. Lists and objects in brackets are embedded in
    the movie document.],
) <fig-schema>

A shortened movie document, as inserted by `insert_data.py`:

```js
{
  _id: 862,
  title: "Toy Story",
  release_date: ISODate("1995-10-30"),
  runtime: 81, budget: 30000000, revenue: 373554033,
  vote_average: 7.7, vote_count: 5415,
  genres: ["Animation", "Comedy", "Family"],
  production_countries: ["US"],
  collection: { id: 10194, name: "Toy Story Collection" },
  keywords: ["jealousy", "toy", "boy", ...],
  cast: [{ id: 31, name: "Tom Hanks", character: "Woody (voice)", gender: "male", order: 0 }, ...],
  crew: [{ id: 7879, name: "John Lasseter", job: "Director", department: "Directing" }, ...]
}
```

The cast is sorted by billing order, and the gender codes are replaced with `"female"`, `"male"` or `null` for unknown. The genres keep their original order, since the first one is the primary genre in task 5. There is a text index on `overview` and `tagline` for task 7, and indexes on `user_id` and `movie_id` in the ratings.

The insertion is done in bulk. The movies are built in Python and inserted with one `insert_many`, and the ratings in batches of 50,000. The whole insertion takes about 3.6 minutes. On disk the movies take 73 MB and the ratings 650 MB plus 567 MB of indexes.

== Part 2: Queries

Each task has its own function in `queries.py`, and the results are printed with tabulate. Most tasks are a single aggregation pipeline, which is MongoDB's version of a SQL query, where the documents pass through stages like `$match` (WHERE), `$group` (GROUP BY), `$sort` and `$project` (SELECT). The new part compared to SQL is `$unwind`, which turns one movie into one document per element of a list, for example one per cast member, so they can be grouped.

Medians are computed in Python from lists the pipeline returns, as `$median` in MongoDB 7.0 only gives an approximate answer. Unknown values are `null` and are skipped by MongoDB's averages, and a person listed twice in the same movie is only counted once. Long results are cut at 20 rows.

=== Task 1

#prompt[Considering only crew with job = Director, which 10 directors with ≥ 5
  movies have the highest median revenue? Also report each director's movie
  count and mean vote_average.]

The pipeline unwinds the crew, keeps the directors, and groups by director, collecting the revenues of their movies. Since most movies have no known revenue, we require 5 movies with a known revenue rather than just 5 movies, otherwise the median would be computed from one or two values. 382 directors qualify. David Yates is on top with a median of \$936 million, which comes from the Harry Potter movies, followed by Peter Jackson and George Lucas. Eric Darnell and Tom McGrath have the exact same numbers since they directed the Madagascar movies together.

#task-output(1)

=== Task 2

#prompt[List actor pairs have co-starred in ≥ 3 movies together, their number
  of co-appearances, and their average movie vote_average. Sort by number of
  co-appearances.]

For each movie the pipeline makes every pair of actors by unwinding the cast twice and keeping the pairs where the first id is smaller than the second, so each pair appears once. That is about 6.5 million pairs, which are grouped and counted. 45,650 pairs have co-starred in at least 3 movies. On top are Huntz Hall and Leo Gorcey with 35 movies, from The Bowery Boys series, then Charlie Chaplin and Edna Purviance, and Laurel and Hardy. Several of the pairs are voice actors, like Frank Welker and Jim Cummings, who are in many animated movies. This is the slowest query at about 46 seconds, and it needs `allowDiskUse` since the grouping is too big for MongoDB's memory limit.

#task-output(2)

=== Task 3

#prompt[List the top 10 actors (with ≥ 10 credited movies) that have the widest
  genre breadth. Report the actor, the number of distinct genres they've
  appeared in, and up to 5 example genres.]

We group by actor and merge the genre lists of their movies with `$setUnion`. The problem is that many actors have appeared in all 20 genres, so the top 10 is a tie. We break the tie by the number of movies, so the list is the most active actors that have done every genre, with Christopher Lee on top with 148 movies. The examples are the first 5 genres in alphabetical order, which is why they are the same for everyone.

#task-output(3)

=== Task 4

#prompt[For film collections (belongs_to_collection.name not null) with ≥ 3
  movies, which 10 collections have the largest total revenue? For each, report
  movie count, total revenue, median vote_average, and the earliest → latest
  release date.]

We group the movies by collection and sum up the revenue, and the median vote is computed in Python. Harry Potter has the largest total with \$7.7 billion from 8 movies, just ahead of Star Wars, while James Bond needs 26 movies to get to \$7.1 billion. The `with_revenue` column shows how many of the movies have a known revenue. For Despicable Me only 4 out of 6 do, so its real total is higher.

#task-output(4)

=== Task 5

#prompt[By decade (e.g., 1970s, 1980s, …) and primary genre (first element in
  genres), what is the median runtime and movie count? List results sorted by
  decade then median runtime (desc).]

The decade is computed from the release date in the pipeline, and the primary genre is the first element of `genres`. Movies without a release date, runtime or genre are left out. The earliest decades are dominated by very short films, as many of the films from the 1890s are about a minute long. From the 1930s and onwards the medians settle between about 85 and 105 minutes for most genres. War and History are often the longest, and from the 1910s on Animation is the shortest in every decade, since many of those are short films. Some groups only have one or two movies, like Science Fiction in the 1940s at 220 minutes, so their medians don't say much.

#task-output(5)

=== Task 6

#prompt[For each movie's top-billed 5 cast (by order), what is the proportion
  of female cast? Aggregate by decade and list decades sorted by average female
  proportion (desc), including movie counts used. Unknown gender may be
  ignored.]

For each movie we take the first 5 cast members by billing order, ignore those with unknown gender, and compute the share of women. Movies where all 5 have unknown gender are left out. The top of the list are decades with only one or two movies, like the 1870s and 2020s, so these don't mean much. For the decades with enough movies the share is surprisingly stable, from 31% in the 1970s to 38% in the 2010s. Since 40% of the cast has unknown gender, the numbers would change if the unknowns are not spread evenly between women and men.

#task-output(6)

=== Task 7

#prompt[Using a text search over overview and tagline, which 20 movies matching
  "noir" or "neo-noir" (and vote_count ≥ 50) have the highest vote_average?
  Return title, year, vote_average, and vote_count.]

This uses `$text` with the text index on `overview` and `tagline`. The text index splits "neo-noir" into the words "neo" and "noir", so searching for "noir" finds both. Searching for "neo-noir" would also match any overview with "neo" in it, like The Matrix Reloaded, which is 48 movies in total. Only 5 movies match with at least 50 votes, so the list is shorter than 20. We checked this with a regular expression, and only 82 movies mention "noir" at all, some of them only in the name Renoir. The three highest rated are classic films from Japan and France.

#task-output(7)

=== Task 8

#prompt[Which 20 director–actor pairs with ≥ 3 collaborations (same movie) have
  the highest mean vote_average, considering only movies with vote_count ≥
  100? Include the pair's films count and mean revenue.]

For each movie with at least 100 votes we unwind both the directors and the cast, and group by the pair. A director acting in their own movie is not counted as a pair. The list is dominated by Akira Kurosawa, who used the same actors across his films, with Coppola and John Cazale from The Godfather and Peter Jackson with the Lord of the Rings actors in between. The mean revenue is low or empty for the Japanese films, since few of them have a known revenue.

#task-output(8)

=== Task 9

#prompt[Among movies where original_language ≠ "en" but at least one
  production company or country is United States, which are the top 10
  original languages by count? For each language, report the count and one
  example title.]

The production companies don't have a country in the dataset, so a company only counts if its name says United States, and otherwise we use the production countries. As the example title we pick the most popular movie of each language. French is clearly on top with 112 movies, with Leon: The Professional as the example, followed by Spanish and Italian. `xx` means no language, and fittingly the example is Quest for Fire, where the characters speak a made up language.

#task-output(9)

=== Task 10

#prompt[For each user, what is their ratings count, population variance of
  ratings, and number of distinct genres rated? List the top 10 most
  genre-diverse users, and separately the top 10 highest-variance users (only
  users with ≥ 20 ratings).]

The pipeline groups the 26 million ratings by user and computes the count and population standard deviation with `$stdDevPop`, which we square to get the variance. The genres are found in Python, by looking up the genres of each rated movie in a dictionary of all 45,433 movies. This is faster than a `$lookup` for every rating, and the whole task takes about 28 seconds. We apply the limit of 20 ratings to both lists, which leaves 166,274 users.

For the genre diversity, 2,896 users have rated all 20 genres, so it is a big tie, which we break by the number of ratings. User 45811 is on top with 18,223 ratings. The highest variance is 5.06, which is the largest possible, as it comes from users who only gave ratings of 0.5 and 5.0, half of each.

#task-output(10)

= Discussion

We used Docker locally instead of the VM from NTNU, since it was quicker to set up and a laptop is faster than the VMs. We used uv instead of pip, with the same pinned versions as `requirements.txt`.

Most of the work in this assignment was in the cleaning, and it was a different kind of messy than the Porto dataset. There the problems were in the values themselves, like GPS jumps, while here the problem was the format, with split rows, Python literals instead of JSON, and zeros and placeholders meaning unknown. Several of these don't cause an error, they just give wrong numbers, like a director with a median revenue of 0 or a movie being counted twice after a join. A big part of the EDA was therefore checking each decision, for example that the repeated ids in `credits.csv` really list the same people before dropping them.

MongoDB made the schema a lot simpler than it would have been in MySQL. Instead of eight or so tables with foreign keys, the movie is one document, and most queries don't need a join at all. The trade-off is that the data is duplicated, as an actor's name is stored in every movie they are in, and if it changes it has to be updated everywhere. For a dataset that is read and not updated that is fine. The ratings show where embedding stops making sense, as they are huge, keep growing, and are also queried per user.

The aggregation pipelines took some getting used to compared to SQL, as they are longer and written as nested dictionaries. On the other hand it is easy to follow what happens step by step, and things like making pairs of actors are simpler with `$unwind` than with self joins in SQL. We used a mix of the database and Python. Grouping and counting is done in MongoDB, while exact medians and the genre lookup in task 10 are done in Python on what comes back. This means more data is sent back for some tasks, but all ten queries still run in about a minute and a half.

Many of the tasks also turned out to depend on interpretation, like whether the 5 movies in task 1 need a known revenue, what counts as a production company being from the United States, or how to break the ties in task 3 and 10. We tried to pick the reading that gives meaningful results and to state it for each task.

From this assignment we learned how to design a document schema and when to embed and when to reference, which is quite different from normalising tables. We also learned how much of the work with a real dataset is in finding problems that don't show up as errors.

= Feedback

The dataset is not part of the files we were given, so it has to be downloaded from Kaggle separately. Part 1 of the tasks says to "analyze and clean the Porto dataset", which seems to be left over from assignment 2, and the database setup refers to the wrong step numbers in a couple of places. The tips also mention `sudo mongo`, which is replaced by `mongosh` in MongoDB 7.0. In `example.py`, `show_coll` lists the collections of the `test` database rather than our own, so it always prints an empty list. Some of the tasks were also open to interpretation, so a sentence on how to handle unknown values and ties would have helped. Other than that the assignment was great, and the dataset was a nice fit for a document database.

= AI use <ai-use>

In this assignment we used AI. It was used to help find entrypoints to do EDA on before we expanded and made cleaning decisions. AI also helped set up the report structure in typst, a language similar to latex. It was also used as a learning tool for learning how to write MongoDB queries manually, as neither of us have experience with this and are used to ORMs for document databases, like google firestore.

= Appendix: EDA output

The full output of `eda.py`, one box per step.

#for n in range(1, 9) {
  eda-step(n)
}
