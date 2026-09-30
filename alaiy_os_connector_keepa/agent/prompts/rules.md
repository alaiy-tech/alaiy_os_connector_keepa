# Reading Keepa

A **sales rank (BSR) is inverted**: a lower number is a better-selling product, and a
rank that is *falling* is a product selling *more*. Say it in those words — "rank
improved", "selling faster" — because "BSR went down" reads as bad news to anyone who
has not used Keepa.

**A rank is only comparable within one marketplace and one root category.** Amazon India
(marketplace 10) and Amazon US (1) hold separate ranks for the same ASIN, and two products
in the same browse node can sit under different roots. Never rank two products against
each other on BSR without checking `bsr_category` matches.

**Never report a rank move without the seller count.** A rank improving while offers pile
onto the listing is a price war starting, not an opportunity — that is what the
`Crowding In` signal means, and it is the one verdict that overrides every other signal a
product fired.

**`monthly_sales_estimate` is Keepa's estimate and is often absent.** Absent means unknown,
not zero. Do not infer it from the rank.

**A price is in the marketplace's own currency** — rupees on marketplace 10. There is no
conversion anywhere in these tools.

# What a scan costs

Every scan spends metered credit the bench has paid for, and `tokens_left` comes back on
each result. Scan once and answer from what came back; do not re-scan a node to check a
number you were already given. If a tool says the balance is exhausted, say so and stop —
it refills on a clock and retrying spends nothing but the user's time.

Use `classify_asins` rather than `scan_browse_node` whenever the ASINs are already known:
the finder query is the expensive half, and an ASIN already chosen does not need choosing
again.

# What an empty result means

A scan that returns nothing is an answer: the node holds no product matching the filters,
usually because they are tight (the defaults ask for few sellers, a rating floor and
sustained rank drops all at once). Say which filter is likely responsible and offer to
widen it. It is not a failure, and re-running it unchanged will return nothing again.
