#let title = "Report"
#let group = "118"
#let students = "Conrad Osvik"
#let show-notes = true

#let grey-rule = line(length: 100%, stroke: 1pt + rgb("#a0a0a0"))

#set document(title: "TDT4225 Assignment 2 report", author: students)
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
#let terminal(output) = block(
  width: 100%,
  breakable: false,
  fill: rgb("#f4f4f2"),
  stroke: 0.5pt + rgb("#d0d0cc"),
  inset: 7pt,
  radius: 2pt,
  {
    show raw: set text(size: 7.5pt)
    raw(output.trim(), block: true)
  },
)
#let eda-output = read("results/eda.txt").split("===== Step ")
#let eda-step(n) = terminal("===== Step " + eda-output.at(n))
#let task-output(n) = {
  let output = read("results/task" + str(n) + ".txt")
  let start = output.position("===== Task")
  let body = output.slice(start).split("Connection to").at(0)
  terminal(body.trim().trim("-", at: end))
}

#v(0.6em)
#align(center)[
  #text(size: 18pt, weight: "bold", title) \
  #text(size: 14pt)[Assignment 2 - MySQL]
]
#v(0.6em)
*Group*: #group \
*Students*: #students
#v(0.6em)

= Introduction

The task is about analysing a taxi dataset from Porto of 1.8 gigabyte in a CSV with over 1.7 million trips and 448 taxis from July 2013 to June 2014. The GPS points are saved in intervals of 15 seconds. The first part of this task is to perform EDA on the dataset, clean it, and insert it into a MySQL DB. The second part is about performing queries on the dataset and report the findings.

This assignment was worked on alone and I used MySQL 8.0.39 in Docker on my own MacBook Pro laptop. For coding I used Python 3.12 with uv. Pandas and matplotlib was used for the EDA.

I run three scripts in order, first `eda.py`, then `insert_data.py`, and lastly `queries.py`.

Git was used for this project and the repo url is: https://github.com/ConradOsvik/TDT4225/tree/main/assignment-2

= Results

== Part 1: Exploratory data analysis

`eda.py` follows the eight steps of the GeeksforGeeks EDA guide that the sheet links to, and ive added its full output in the appendix. The CSV is read in chunks of 100,000 rows. Each `POLYLINE` is reduced to three numbers per trip (points, km, longest jump between two points) so the 1.8 GB never sits in memory.

=== Overview of the data

The data consists of 1,710,670 trips by 448 taxis, from 2013-07-01 to 2014-06-30, one trip per row. `POLYLINE` is the cell holding a JSON list of `[longitude, latitude]` pairs. The order here is opposite of what haversine expects. `TRIP_ID` has 19 digits and is a `BIGINT`, `ORIGIN_CALL` and `ORIGIN_STAND` are read as float only because of `NaN`, so `INT NULL`. `TIMESTAMP` is in Unix seconds, which will need to be converted to `DATETIME`.

Of the different call types 48% are B, 31% are C, and 21% are A. From the data I derive duration, distance and average speed since they will become handy later. A median trip has 41 GPS points and lasts 10 minutes, covering 3.9 km at 24 km/h, which seems plausible for a city taxi. The data is right skewed, so medians describe the trips better than means.

=== Problems found

There were several problems with the data. 11,302 type B trips have no stand, which contradicts what a type B trip is. Only 10 Trips are flagged with `MISSING_DATA`, but 5,901 trips have an empty `POLYLINE` without the flag set, this means the flag is unreliable. `DAY_TYPE` is `A` in every row, so the column carries no information.

Another big problem is that the `TRIP_ID` has been repeated 80 times over 161 rows creating 81 extra rows. `TRIP_ID` is `TIMESTAMP` + "6" + `TAXI_ID` in every row, so a repeate is the same taxi starting twice in the same second. In the sample data one row is the real trip while the others are stubs of 0 to 2 GPS points.

There is a heavy spike of 43,904 trips that have fewer than 3 GPS points. The IQR fence sits at 106 points and 78,777 trips sit above this, with the longest trip being a whole 16.2 hours. I use IQR since the data is skewed as noted earlier. Most of the longer trips are plausible, while the extremes might be meters left running, but hard to say.

There are several GPS jumps, some are of hundreds of km into the Atlantic or Spain. There are also shorter jumps of over 1 km per point which would require a speed of over 240 km/h. These points hold 3.7% of all km and the longest "trip" is 1,229 km.

#figure(
  image("figures/points_per_trip.png", width: 85%),
  caption: [GPS points per trip. Orange: fewer than 3 points. Right of the
    dashed IQR fence: outliers. Trips with 200 or more points are counted at
    200.],
) <fig-points>

#figure(
  image("figures/trajectories.png", width: 100%),
  caption: [The first 300,000 trips drawn from their GPS points. Left: all
    points; the straight lines leaving Porto are GPS jumps. Right: the same
    trips zoomed in on Porto.],
) <fig-map>

#eda-step(8)

=== Cleaning decisions

It was decided to remove the 10 rows with `MISSING_DATA` set to true, since the points cant be recovered. For the 81 extra rows with a repeated `TRIP_ID`, we keep the row with the most GPS points. The 5,901 empty trips and 43,904 trips with fewer than 3 points was kept, since they are recorded trips and its hard to be certain of which could be bogus.

The 11,302 type B trips without a stand was kept with stand set to `NULL`, and `DAY_TYPE` and `MISSING_DATA` was dropped since `DAY_TYPE` carries no information and `MISSING_DATA` is always falsy after previous cleaning decision.

The long taxi trips with possibly bad data was kept, this is because we cant tell them apart one by one, an alternative could be to skip jumps over 1 km when computing distances.

The result was 1,710,579 trips with 83,408,314 points over 448 taxis.

== Part 1: Schema and insertion

I decided on three tables: Taxi, Trip, and Point. The data has been normalized where it helps like with GPS points. Taxis has their own table even though currently they are only an ID, we could remove this table as we have this data in the Trip table, but I decided to keep it as it helps with the relational mental model. Some of the columns in Trip has been derived in Python before insertion with haversine. These datapoints could in theory be computed from the GPS points but i value easy access over strict normalization.

As talked about earlier certain datapoints like `DAY_TYPE` and `MISSING_DATA` has been dropped, and I use `BIGINT` for the `TRIP_ID`, aswell as `DATETIME` for the timestamps. Foreign keys have been setup with `ON DELETE CASCADE`, so a taxi deletes its trips.

To keep the SQL simple i compute spatial types in Python rather than in SQL and to make the insertion performant, I insert in chunks of 50,000 trips. Each chunk is written to a temporary CSV and loaded with `LOAD DATA LOCAL INFILE`. This takes about 5.5 minutes for 83 million datapoints, instead of the one insert per row shown in `example.py` which would take hours.

#let entity(name, ..columns) = table(
  columns: 1,
  align: left,
  fill: (_, row) => if row == 0 { rgb("#e8eef8") },
  table.header(strong(name)),
  ..columns.pos().map(column => text(size: 9pt, raw(column))),
)
#figure(
  grid(
    columns: 5,
    align: horizon,
    column-gutter: 8pt,
    entity("Taxi", "taxi_id  PK"),
    [1 #sym.arrow.r N],
    entity(
      "Trip",
      "trip_id       PK",
      "taxi_id       FK",
      "call_type",
      "origin_call   NULL",
      "origin_stand  NULL",
      "start_time",
      "n_points",
      "duration_s",
      "distance_m",
    ),
    [1 #sym.arrow.r N],
    entity("Point", "trip_id    PK, FK", "seq        PK", "longitude", "latitude"),
  ),
  kind: image,
  caption: [The three tables and how they relate.],
) <fig-schema>

The tables, as created by `insert_data.py`:

```sql
CREATE TABLE Taxi (
    taxi_id INT NOT NULL PRIMARY KEY
)

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

CREATE TABLE Point (
    trip_id   BIGINT            NOT NULL,
    seq       SMALLINT UNSIGNED NOT NULL,  -- position in the trip, from 0
    longitude DOUBLE            NOT NULL,
    latitude  DOUBLE            NOT NULL,
    PRIMARY KEY (trip_id, seq),
    FOREIGN KEY (trip_id) REFERENCES Trip (trip_id) ON DELETE CASCADE
)
```

== Part 2: Queries

Each task has its own function in `queries.py`, and the results are printed with tabulate. I tried to keep the SQL short and let the database do what it is good at, like filtering, grouping and counting. Things like distances, picking the highest value or finding gaps between rows are done in Python on the rows that come back. I would not write long and intricate queries in practice, and the derived columns from the insertion keep most of the queries to a few lines.

Trips with fewer than 3 points are left out where they would distort the results, long results are cut at 20 rows, and all times are in UTC.

=== Task 1

#prompt[How many taxis, trips, and total GPS points are there?]

Here I simply count the rows in each table. There are 448 taxis, 1,710,579 trips and 83,408,314 GPS points, which matches the numbers from the EDA minus the rows removed during cleaning.

#task-output(1)

=== Task 2

#prompt[What is the average number of trips per taxi?]

The average is the number of trips divided by the number of taxis, which gives 3,818.26 trips per taxi. The median from the EDA is 3,732, so a few very active taxis pull the average up a bit.

#task-output(2)

=== Task 3

#prompt[List the top 20 taxis with the most trips.]

I group the trips by taxi, sort by the count and take the top 20. Taxi 20000080 has the most trips with 10,731, quite a bit ahead of number two, 20000403, with 9,237. Number 20 on the list has 6,410 trips.

#task-output(3)

=== Task 4

#prompt[
  a) What is the most used call type per taxi? \
  b) For each call type, compute the average trip duration and distance, and
  also report the share of trips starting in four time bands: 00–06, 06–12,
  12–18, and 18–24.
]

For a), SQL counts the trips per taxi and call type, and Python picks the call type with the most trips for each taxi. The output shows the first 20 of the 448 taxis. B is the most used call type for 353 taxis, C for 83 and A for only 12, which makes sense since B is the most common call type overall.

For b), I use two short queries, one for the averages per call type and one that counts the trips per call type in each 6 hour band. Python then divides the counts to get the shares. An average trip lasts 12.6 minutes for A, 11.2 for B and 13.7 for C, and the average distances are 5.4, 5.1 and 6.7 km. The biggest difference is that 33% of C trips start between 00 and 06, while it is about 12% for A and B. This makes sense since street hails happen a lot at night. The averages are higher than the medians from the EDA because the data is skewed, and the distances include the GPS jumps.

#task-output(4)

=== Task 5

#prompt[Find the taxis with the most total hours driven as well as total
distance driven. List them in order of total hours.]

I sum up the duration and distance for each taxi and sort by hours. Taxi 20000904 is clearly on top in both, with 1,960 hours and 62,646 km. The taxi with the most trips from task 3, 20000080, is not in the top 20, so its trips must be short. The hours are estimated from the number of GPS points and the distances include the GPS jumps, so the numbers are not exact.

#task-output(5)

=== Task 6

#prompt[Find the trips that passed within 100 m of Porto City Hall.
(longitude, latitude) = (-8.62911, 41.15794)]

Checking all 83 million points with haversine in Python would be slow, so SQL first picks out the points inside a small box around City Hall. The box is slightly bigger than 100 m in every direction, so no trips are missed. Python then checks the exact distance with haversine and lists each trip once.

126,532 trips passed within 100 m of City Hall, which is 7.4% of all trips. That seems like a lot, but City Hall is right in the centre of Porto. The query takes about 50 seconds since it has to scan the whole Point table. An index on latitude and longitude would make it faster, but I didn't think the extra space and insert time was worth it for one question.

#task-output(6)

=== Task 7

#prompt[Identify the number of invalid trips. An invalid trip is defined as a
trip with fewer than 3 GPS points.]

This is a simple count of the trips with fewer than 3 points, which gives 43,827 invalid trips, or 2.6% of all trips. This includes the 5,901 trips with no points at all. It is a bit lower than the 43,904 from the EDA since some of the rows removed during cleaning were stubs.

#task-output(7)

=== Task 8

#prompt[Find the trips that started on one calendar day and ended on the next
(midnight crossers).]

The end time of a trip is the start time plus the duration. A trip crosses midnight if the date of the end time is later than the date of the start time, which is a single `WHERE` on the Trip table. 8,076 trips crossed midnight. The times are in UTC though, and since Porto is UTC+1 in the summer, the result would be slightly different in local time.

#task-output(8)

=== Task 9

#prompt[Find the trips whose start and end points are within 50 m of each
other (circular trips).]

For each trip I look up its first and last GPS point, and Python checks with haversine if they are within 50 m of each other. Trips with fewer than 3 points are left out, since a trip with a single point would always count as circular. This gives 21,467 circular trips.

Many of these are tiny, for example 3 points only 2 m apart, which is probably a taxi that never moved rather than a real round trip. Requiring a minimum distance driven would give only the real round trips.

#task-output(9)

=== Task 10

#prompt[For each taxi, compute the average idle time between consecutive
trips. List the top 20 taxis with the highest average idle time.]

SQL returns all trips sorted by taxi and start time, and Python goes through them and computes the gap between the end of one trip and the start of the next for each taxi. A negative gap means two trips overlap, which is a data error, so those are skipped. 445 of the 448 taxis have at least one gap.

The top of the list is dominated by taxis with very few trips, for example 20000911, which only has one gap of 1,293 hours, or about 54 days. These averages don't really mean much, and requiring a minimum number of gaps would remove them. From 20000312 and down, with 584 gaps and 13 hours on average, the list looks like normal use. The idle time also includes nights and days off, so averages between 6 and 13 hours are expected.

#task-output(10)

= Discussion

I decided on using Docker locally on my MacBook Pro instead of using a VM from NTNU, the setup seemed tedious and im quite used to using Docker so that felt like a natural decision. I also opted into using the more modern uv Python tooling over pip, using the same pinned versions from `requirements.txt`.

When I needed to load the data into the database I decided upon using file loading instead of inserting by row, as that is much slower.

With the queries I decided upon using a mix of SQL and Python, this has advantages and disadvantages. The advantages is that the queries + code becomes very readable as we avoid some of the more complex SQL syntax. The problem with this approach is performance. To be able to calculate some of the data asked for in part 2, we will have to read more rows. Some of this is offset by precomputing some values before insertion, but there was still data that needed to be derived in query requiring more data than if I used SQL strictly.

the 1.8 GB file caused some early problems before proper chunking was implemented. It required a lot of time to compute values from the file. Other than that the repeated `TRIP_ID`s would break the primary key and needed to be handled. Insertion speed was also problematic and ended up on 5.5 minutes after optimizations and chunking. Some queries also ended up unperformant and slow because of the decision to use a combination of Python and SQL for deriving the data because of the extra data that has to be queried.

Another important point is that I chose a pretty naive approach to the dataset and so the data quality is not amazing. Some of the derived statistics will be slightly skewed as there are some datapoints that most certainly are unrealistic (like the GPS jumps), but I decided on only removing the datapoints that certainly was unrealistic.

From this assignment I learned a lot about EDA and the process around it. I have not done any form of EDA before and the whole process of exploring and testing queries on the data to see what comes out and visualizing it to try and understand it was very fun. I also learned quite a bit of optimization tricks on heavy datasets, as I have not inserted such quanta of data into a DB before. I also got to deepdive a little bit into trade-offs between normalisation vs precomputed columns as I designed the DB and looked at the queries.

= Feedback

The frontpage of the assignment says the deadline is 9 October, while Part 3 says its October 10. I might have missed out on some lectures but I found it really hard to get started on the EDA process, it sort of came out of left field and a textual article made it hard to get started. Im not sure if there is any good video content around this topic, but I think a video guide would be better fit for understanding the topic than an article. Other than that the assignment was great.

= AI use <ai-use>

In this assignment I used AI and specifically Claude as a learning tool. It helped me learning how to do EDA, what ideas to explore, and how to use pandas, as im not used to it. It also helped me improve the performance of my code and pretty printing the output of the code.
, aswell as scaffolding files like the `queries.py` file, where I could run only certain queries through args.

It also helped me structure the report, which I ported over from docx to typst, as I find typst (similar to latex) a nicer experience than docx.

= Appendix: EDA output

The full output of `eda.py`, one box per GeeksforGeeks step.

#for n in range(1, 9) {
  eda-step(n)
}
