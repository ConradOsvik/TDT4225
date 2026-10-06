#let authors = "Conrad Osvik"

#set document(title: "TDT4225 - Assignment 1", author: authors)
#set page(
  paper: "a4",
  margin: 24mm,
  header: text(size: 8.5pt)[TDT4225 #h(1fr) Assignment 1],
  footer: context align(center, text(size: 8.5pt)[Page #counter(page).display()]),
)
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en")
#set par(leading: 0.68em)
#set heading(numbering: none)
#set table(inset: 6pt, stroke: 0.5pt + black)

#let prompt(body) = block(inset: (left: 8pt), body)
#let answer(body) = block(width: 100%, inset: (left: 8pt), body)
#let source(body) = text(size: 9pt, fill: rgb("555555"), body)

#align(center)[
  #text(size: 20pt, weight: "bold")[TDT4225 - Assignment 1] \
  Exercise 1 (theory) \
  #authors
]
#v(10pt)

= Question 1: Flash Translation Layer

#prompt[How does the Flash Translation Layer (FTL) work in SSDs?]

#answer[
    NAND flash read and programs pages, but erases larger blocks at a time. Because a page cannot simply be overwritten, the SSD controllers flash translation layer (FTL) maps the logical block to a phyiscal flash location. An update is written to a free location, the old copy becomes invalid and the mapping is changed. The FTL spreads writes across blocks to ensure wear leveling, this includes ocationally moving rarely changed data to different blocks, so a small hot area doesnt wear out long before other blocks. Garbage collection copies still valid pages out of blocks containing invalid pages and then erases those blocks for reuse. These moves cost extra I/O and cause write amplification.
]

= Question 2: Sequential writes

#prompt[Why are sequential writes important for performance on SSDs?]

#answer[
  SSDs have no seek time, but small scattered writes still create many out of place updates and blocks containing both current and outdated pages. To reuse one of these blocks for new data, the SSD moves the current pages elsewhere, then erases the block. That extra copying creates write amplification, latency, and wear. Larger sequential writes can be batched, fill pages and blocks more completely, and use the SSDs internal channels in parallel. They usually sustain higher throughput after the SSD reaches steady state. With sufficiently large, aligned random writes, the performance can end up similar to sequential writes.
 ]

= Question 3: Block alignment

#prompt[Discuss the effect of alignment of blocks to SSD pages. See, for example, Figure 2.5 of Dybvik.]

#answer[
    A write is aligned to pages/blocks when its start adress is on a clustered page boundary and its size is a multiple of the page size. In this case each clustered page can be written as complete unit. Requests smaller or partly bigger than a page end up leaving part of the page untouched. The controller might need to read the old page, combine the unchanged bytes with the new bytes, and write a new page. this increases latency and write amplification. Its important to note that a write of the size of a page is only performent when it aligns with the page. If a page-sized write crosses a boundary, it touches two pages and may need more work than an aligned write.
]

= Question 4: RocksDB table layout

#prompt[Describe the layout of the MemTable and SSTable in RocksDB.]

#answer[
    The *MemTable* is RocksDBs current in memory, sorted key value structure, and its default implementation is a skip list. Writes are also appended to a write ahead log (WAL) so the MemTable can be reconstructed after a crash. When the MemTable reaches its size limit, it becomes immutable and a new MemTable receives writes. The old MemTable is flushed to an immutable SSTable file.

    An *SSTable* stores key value entries sorted by key. In the block based file format, data blocks hold entries, meta blocks contain items such as filters and statistics, the index locates the data blocks, and a footer closes the file. Bloom filters can rule out files that definitely lack a searched key. Flushed SSTables first enter level 0, where keys might colide with older SSTables. At higher levels compaction happens and keys are merged per level to newest value.
]

= Question 5: RocksDB compaction

#prompt[What happens during compaction in RocksDB?]

#answer[
    Compaction reads immutable SSTables, merges their sorted keys, and writes new SSTables. For duplicate keys, it keeps the newest value, obsolete versions and tombstones can be discarded once its safe. The old input files are then replaced by the new files. In leveled compaction overlapping files are merged into the next level so files above level 0 have no conflicting keys per level. This process limits how many files must be inspected on read, but the rewriting / merging process consumes CPU and I/O and adds write amplification.
]

= Question 6: LSM-trees versus B+-trees

#prompt[Give reasons why LSM-trees are regarded as more efficient than B+-trees for large volumes of inserts.]

#answer[
    An LSM-tree appends each insert to a WAL and updates a MemTable, many records are later flushed and merged as large, mostly sequential writes.  The disk I/O cost is therefore spread over the given batch. A B+-tree typically updates a leaf page for a small insert, can split pages, and also logs the change, its in palce page rewrites can cause more small random I/O and SSD work. These differences make LSM-trees attractive for sustained, large insert volumes. But repeated compaction means the total write cost still depends on workload and configuration.
]

= Question 7: Weaknesses of LSM-trees

#prompt[What are the known weaknesses of LSM-trees?]

#answer[
    Reads may have to check the MemTable and several SSTables or levels, especially for older data or keys that are entirely missing. Bllom filters reduce this problem but dont entirely eliminate it. Compaction rewrites data repeatedly which causes write amplification, uses extra temporary space in the process, and competes with foreground reads and writes for CPU and I/O. Old versions and deletion markers remain until suitable compaction removes them, taking up space. If compaction falls behind during a write burst, level-0 files or immutable MemTables accumulate and new writes may slow down. LSM-trees enables fast insertions at the cost of reading and cleaning them up afterwards, which requires more work.
]

= Question 8: Cloud versus self-hosting

#prompt[What are the pros and cons of cloud versus self-hosted systems?]

#answer[
    *Cloud services* makes it quick to obtain managed infrastructure and to scale resource up and down dependent on demand. The proider handles the routine operation, and usage-based billing can reduce costs by not paying for idle capacity. Downsides includes less control of features, tuning, debugging, outages, uncertain cost and fees, provider dependent APIs, data location, privacy, security, and possibly political constraints.

    *Self-hosting* gives full control over hardare, software, data palcement, observability and specialized tuning. For predictable workloads and an experienced team, it can cost less than serverless. It requires capacity planning, aswell as capital or rental costs, maintenance, upgrades, backups, security, and staff able to respond to failures. Renting a VM avoids buying hardware, but you still need people to manage the software, backups, and failures. Planning capacity and scaling the system can still be difficult. The choice is rather a spectrum of choices than a singular choice.
]

= Question 9: Serverless computing

#prompt[Describe the concept of serverless computing or Function as a Service (FaaS).]

#answer[
    Serverless computing runs application functions in response to requests or events without the developer provisioning indivudal servers. The provider starts and scales the execution capacity, then releases it as demand falls. Billing is commonly based on innvocations and execution time. The application still runs on servers, bu their allocation is hidden. Functions are usually short-lived, but this has changed a bit in the AI era, and they should keep durable state in external services since later innvocation can run at a different place either inside the datacenter or in an entirely different datacenter. The biggest benefits of this model is the extreme scalability and simplicity of the model, it essentially creates a facade where you seemingly have infinite compute. Limitations are often the limits of the execution time, although this is changing in the AI era, aswell as supported runtimes and cold-start latency.
]

= Question 10: Sources of failure

#prompt[Regarding fault tolerance, describe what hardware, software, and human errors may be.]

#answer[
    *Hardware faults* are physical failures or disturbances like a disk dying, RAM corrupting bits, a power supply fails, or a whole datacenter losing power. *Software faults* are defects in code or dependencies such as a bug triggered by unusual input, resource exhaustion, or a bad recovery path. They can affect many machines simultaneously when those machines run the same code. *Human errors* include missconfiguration, accidental deletions, commands run in wrong systems, incorrect deployments, and so on. A fault is an underlying problem, it becomes a system failure when the service can no longer meet its expected behaviour.
]

= Question 11: Fault tolerance techniques

#prompt[Give an overview of tasks or techniques you may use to achieve fault tolerance.]

#answer[
    First, define what service must survive and monitor for deviations. Reduce the change of faults by testing and reviewing the code, using safe configuration interfaces, using access control, aswell as using staged releases for easy rollback. Detect failures with health checks, checksums, metrics, alerts and practice recovery drills. Limit outages impact by using redundant disks, power, network paths, aswell as replicating services across machines. Keep durable WALs and backups of data, verify that restoring works, and make sure retries and recovery procedures safe through idempotency so a failed operation can be resumed without causing duplcation or other side effects.
]

= Question 12: SQL and the document model

#prompt[
  Compare SQL and the document model, giving advantages and disadvantages of each.
  Show the problem with many-to-many relationships in the document model using
  papers with many sections and words, and many authors with names and addresses
  who may each have written many papers.
]

#answer[
    *SQLs relational model* stores entities in tables and connects them through keys and joins. A schema, constraints, and transactions help maintain consistency, while joins handle many to many relationships without duplicating entries. Its costs are schema migrations and possibly expensive joins. Some would also say its rigidity can be cumbersome.

    *A document model* keeps related objects together, often represented as JSON, so a paper with ordered sections and their words can be read as one document. It allows for flexible structures and good locality when the whole document is needed. Cross-document relationships and updates to shared data are harder, the document is often too large or duplicated if everything is embedded together.

    For example, a paper document could contain `sections: [{number: 1, words: [...]}, ...]` and `author_ids: [7, 12]`. Separate author documents hold each author's name and address. If we embed full author records in every paper, changing an address requires updating all of that author's papers, embedding all paper data inside every author has the same duplication problem. Keeping IDs avoids duplication but requires cross-document lookups and application-managed references. In SQL, `Paper`, `Section`, and `Author` tables connect through a `PaperAuthor(paper_id, author_id)` many to many join/junction table. Each author can write many papers and each paper can have many authors without copying the author record.
]

= Question 13: Graph model

#prompt[
  When should you use a graph model instead of a document model, and why?
  Give an example of a typical problem that benefits from a graph model.
]

#answer[
    A graph model is great when relationships are numerous, changing and central to queries, especially when queries traverse an unknown number of times. Documents work best when the object is largly self-contained, following many references between documents becomes cumbersome. A graph represents entities a nodes and relationships as edges, making path and neighborhood queries natural.

    For example, a social network of friendships benefits from the graph model. Here each node represents a person, and an edge represents a friendship between two people. Natural queries like who are our mutual friends becomes trivial in such a data structure.
]

= Question 14: Textual encodings

#prompt[What situations favor textual encodings over binary encodings when sending data?]

#answer[
    Textual encoding formats such as JSON, XML, or CSV are great when humans need to read or edit messages, easy inspection is valuable, existing clients already use it, or independent organizations need a broadly supported interchange format without agreeing on i binary schema and toolchain. Text is often sufficient when messages are small and bandwidth or parsing cost is not the deciding factor. Choose binary encoding when compact messages, parsing speed, precise types, or a controlled schema are more important.
]

#pagebreak()
= Question 15: Column compression

#prompt[
  For the column values `43 43 43 87 87 63 63 32 33 33 33 33 89 89 89 33`:
]

== (a) Bitmap

#prompt[Create a bitmap for the values.]

#answer[
  With positions numbered 1 through 16 from left to right, one bitmap per distinct
  value has a 1 exactly where that value occurs:

  #table(
    columns: (auto, 1fr),
    table.header([*Value*], [*Bitmap (positions 1-16)*]),
    [32], [`0000000100000000`],
    [33], [`0000000011110001`],
    [43], [`1110000000000000`],
    [63], [`0000011000000000`],
    [87], [`0001100000000000`],
    [89], [`0000000000001110`],
  )
]

== (b) Run-length encoding

#prompt[Create a run-length encoding for the values.]

#answer[
  Storing each consecutive run as `(value, count)`:
  `(43, 3), (87, 2), (63, 2), (32, 1), (33, 4), (89, 3), (33, 1)`.
  The counts sum to 16.
]

= Question 16: Schema evolution in binary formats

#prompt[
  Compare MessagePack, Apache Thrift, Protocol Buffers, and Avro. If a String
  attribute named "Labour union" is added to a Person structure, how does each
  system support the change? How is forward and backward compatibility supported?
]

#answer[
  An old `Person` record has no `labour_union` field. A new record may have one.
  *Backward compatibility* means a new program can read an old record. *Forward
  compatibility* means an old program can read a new record.

  *MessagePack* stores field names with the values. It has no built-in rules for
  changing the fields. The new program must accept that `labour_union` is missing
  from old records. The old program must ignore the extra name in new records.

  *Apache Thrift* gives each field a number. By giving `labour_union` a new number and
  making it optional, the old program skips a number it does not know. The new
  program accepts old records where the field is missing.

  *Protocol Buffers* also gives each field a number, called a tag. Giving
  `labour_union` a new tag and keeping the old tags unchanged, the old program skips
  the new tag. The new program can read an old record and treat the missing String
  as empty or absent.

  *Avro* uses one schema to write a record and another to read it. Adding
  `labour_union` with a default value, for example an empty string, causes a new reader
  to use that default value for old records. An old reader ignores the extra field in new
  records. Avro does not put field names in each record, so the reader also needs the schema that was used to write it.
]

#pagebreak()
= Question 17: Replication

== (a) Multi-leader and leader-based replication

#prompt[
  When should you use multi-leader replication, and why? When is leader-based
  replication better?
]

#answer[
    Multi-leader replication lets several nodes accept writes. It is useful across distant data centers when users need local write latency and a site should continue accepting writes during a wide.area link or data-center outage. It also fits occasionally disconnected clients that synchronized later. The cost of Multi-leader replication is that writes to the same data can happen concurrently and must be detected and resolved, cross-site ordering and consistency becomes harder.

    Single-leader replication is preferable when writes can be routed to one available leader and a clear order of changes, simpler conflict handling, and stronger consistency are more valuable than local writes at every site. Followers can serve reads and take over after leader failure, subject to replication lag and failover behavior.
]

== (b) Log shipping

#prompt[Why use log shipping for replication instead of replicating SQL statements?]

#answer[
    Replaying SQL statements on followers requires the statements to produce the same result everywhere. That can fail for `NOW()`, `RAND()`, auto-generated IDs, triggers, side effects, or differing concurrent execution order. Shipping a write-ahead log instead sends the leaders recorded changes and commit order, followers replay those changes to reproduce the leaders state without re-evaluating nondeterministic SQL. Physical WAL shipping can be efficient but couples replicas to the leaders storage format and often database version. Logical row-based logging avoids some of that coupling by shipping row changes rather than physical page updates
]

= References

- Håvard Dybvik. _Evaluating the Potential of LSM-Trees to Supersede B-Trees in Databases_, Chapter 2 (course extract, `dybvik-extract.pdf`).
- Martin Kleppmann and Chris Riccomini. _Designing Data-Intensive Applications_, 2nd ed., Chapters 1, 3, and 5 (course PDF).
- Svein Erik Bratsberg. TDT4225 lecture slides: _Chapter 1 - Trade-Offs in Data Systems Architecture_, _Chapter 2 - Defining Non-Functional Requirements_, _Chapter 3 - Data Models and Query Languages_, _Chapter 4 - Storage and Retrieval_, _Chapter 5 - Encoding and Evolution_, and _Chapter 6 - Replication_ (course PDFs).
- Håvard Dybvik and Svein Erik Bratsberg. _SSDs, LSM-trees and RocksDB_ (course slides, `lsm.pdf`).
