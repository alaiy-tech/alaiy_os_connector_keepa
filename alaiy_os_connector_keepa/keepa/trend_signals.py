# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""The four Keepa patterns worth acting on, read off a product's own history.

A current rank against its 90-day average says which way a listing is pointing, and that
is all it says. It cannot separate the two cases sourcing actually cares about:
a rank that collapsed in six weeks (new demand, probably still uncrowded) and one that
drifted down steadily across a year (an established product, already contested). Both
read as "improving".

So this module reads the SHAPE of the move instead, over three windows, across three
series -- rank, price and seller count -- and names the pattern:

    fast_mover      rank fell hard inside 30-60 days, few sellers. The opportunity window.
    steady_climber  rank improved consistently over ~6 months, price flat. Lower risk.
    price_dip       rank held, buy box price recently dropped. An entry moment.
    crowding_in     seller count spiked while rank did not improve. Someone else found it.

A product can carry more than one -- crowding_in and fast_mover together is a window that
opened and is closing -- so `classify` returns every signal that fires, and a `verdict`
that resolves them: crowding_in is disqualifying whatever else is true, because the
arithmetic that follows (a landed cost against a buy box price) is computed off a price
that is about to be competed down.

Input is three decoded series -- `keepa/history.py`'s `parse_series` output, one each for
sales rank, price and offer count -- plus the current values. Nothing here reads the Keepa
wire format and nothing spends a token: a classification is a second opinion on data a
scan has already paid for, which is why it is free to run over a whole result set.
"""

from datetime import date, datetime

FAST_MOVER = "fast_mover"
STEADY_CLIMBER = "steady_climber"
PRICE_DIP = "price_dip"
CROWDING_IN = "crowding_in"

ACT = "act"
WATCH = "watch"
AVOID = "avoid"

#: A signal's human name, for a card that shows the verdict rather than the slug.
LABELS = {
    FAST_MOVER: "Fast Mover",
    STEADY_CLIMBER: "Steady Climber",
    PRICE_DIP: "Price Dip Opportunity",
    CROWDING_IN: "Crowding In",
}

#: Fast mover: the rank has to have improved by this much inside the short window. 0.5 is
#: a halving -- the doc's worked example (500,000 -> 71,000 in 45 days) is 0.86, so this
#: is well below the case it was drawn from and still far outside ordinary drift.
_FAST_IMPROVEMENT = 0.50
_FAST_WINDOW_DAYS = 60

#: Steady climber: smaller total improvement, but over a window where drift alone does not
#: produce it, and it has to be *consistent* -- see `_consistency`.
_STEADY_IMPROVEMENT = 0.25
_STEADY_WINDOW_DAYS = 180
_STEADY_CONSISTENCY = 0.6

#: Price stability for a steady climber, and the drop that makes a price dip. Both measured
#: against the value at the start of the window, not against an average, because an average
#: that already contains the drop hides it.
_PRICE_STABLE = 0.10
_DIP_DROP = 0.10
_DIP_WINDOW_DAYS = 30

#: Crowding: both a relative and an absolute rise, because on a listing with two sellers a
#: third is +50% and means very little, and on one with forty a spike of three is noise.
_CROWD_RATIO = 1.5
_CROWD_ABSOLUTE = 3

#: Above this, a listing is crowded on its current count alone -- no history needed. The
#: doc's own filter stops at 8 sellers.
_CROWDED_SELLERS = 8

#: How much of a window the history has to actually cover before it is read. A series that
#: reaches back 12 days cannot answer a question about 60, and answering it anyway -- by
#: treating the oldest point available as "60 days ago" -- turns a fortnight of ordinary
#: movement into a fast mover.
_WINDOW_COVERAGE = 0.7


def _points(series):
    """A decoded history series as [(days_ago, value)].

    Takes `parse_series`'s `{"time": iso, "value": n}` points, and tolerates a `date`/
    `price` shape as well so a caller holding an already-summarised series does not have
    to rebuild it. A point with no value is dropped rather than read as zero -- Keepa's
    -1 already means "no data here", and the decoders above return None for it.
    """
    today = date.today()
    points = []
    for entry in series or []:
        value = entry.get("value", entry.get("price"))
        stamp = entry.get("time") or entry.get("date")
        if value is None or not stamp:
            continue
        try:
            when = datetime.fromisoformat(stamp).date()
        except (TypeError, ValueError):
            continue
        points.append(((today - when).days, float(value)))
    return points


def _then(points, days_ago):
    """The value closest to `days_ago`, or None when the series does not reach back there.

    Keepa history is sampled, not daily, so "60 days ago" is whichever observation sits
    nearest that mark -- but only if the series spans enough of the window to have one
    (`_WINDOW_COVERAGE`). Returning the oldest point regardless is the failure mode this
    guard exists for: it makes every short-history product look like it moved a long way.
    """
    if not points:
        return None
    if max(age for age, _ in points) < days_ago * _WINDOW_COVERAGE:
        return None
    return min(points, key=lambda point: abs(point[0] - days_ago))[1]


def _now(points):
    """The most recent observation -- the smallest days_ago, not the last element: a
    series is ordered by time, and a caller that has concatenated two is not."""
    return min(points, key=lambda point: point[0])[1] if points else None


def _improvement(before, after):
    """How far a rank improved, as a fraction of where it started.

    A LOWER sales rank is a better one, so this is positive when `after` is the smaller
    number. Returns None rather than 0.0 when there is nothing to compare, because "did
    not move" and "cannot say" lead to different verdicts.
    """
    if not before or not after or before <= 0:
        return None
    return (before - after) / before


def _consistency(points, days):
    """The share of consecutive steps inside `days` that improved the rank.

    This is what separates a steady climber from a fast mover with a long tail: both end
    the window far below where they started, but one got there in a straight line and the
    other in a single jump. Measured on steps rather than on a fitted slope because the
    series is unevenly sampled, and a regression over uneven spacing weights whichever
    stretch Keepa happened to observe most.
    """
    window = sorted((point for point in points if point[0] <= days), reverse=True)
    if len(window) < 4:
        return None
    steps = [window[i][1] - window[i + 1][1] for i in range(len(window) - 1)]
    improved = sum(1 for step in steps if step > 0)
    return improved / float(len(steps))


def _signal(name, strength, detail):
    return {"signal": name, "label": LABELS[name],
            "strength": round(min(max(strength, 0.0), 1.0), 2), "detail": detail}


def classify(product):
    """Every signal a product's history fires, plus the verdict they add up to.

    `product` is a dict carrying `bsr_history` / `price_history` / `seller_count_history`
    (decoded series) and the current `bsr` / `price` / `seller_count`. It is a plain dict
    rather than a Keepa product object because the caller has usually already shaped one
    for its own screens, and asking it to hand the raw record back would mean decoding
    the same csv twice.

    Returns `{signals, verdict, score, reasons}`. `score` ranks one candidate against
    another in the same scan and is not a probability: it is the strongest supporting
    signal's strength, zeroed for anything the verdict says to avoid, so that sorting a
    result set on it puts the actionable products first and the contested ones last.

    A product with no signal at all is not a failure -- most of a scan is that -- and it
    comes back as `watch` with an empty list.
    """
    bsr = _points(product.get("bsr_history"))
    price = _points(product.get("price_history"))
    sellers = _points(product.get("seller_count_history"))

    bsr_now = _now(bsr) or product.get("bsr")
    price_now = _now(price) or product.get("price")
    sellers_now = product.get("seller_count") or _now(sellers)

    fast = _improvement(_then(bsr, _FAST_WINDOW_DAYS), bsr_now)
    steady = _improvement(_then(bsr, _STEADY_WINDOW_DAYS), bsr_now)

    price_then_steady = _then(price, _STEADY_WINDOW_DAYS)
    price_then_dip = _then(price, _DIP_WINDOW_DAYS)
    price_move = _improvement(price_then_steady, price_now)  # positive = price fell
    dip = _improvement(price_then_dip, price_now)

    sellers_then = _then(sellers, _FAST_WINDOW_DAYS)

    signals = []

    # 01 Fast Mover. The seller test is on the current count, not on the history: a
    # listing that is crowded today is crowded whatever it looked like in August.
    if fast is not None and fast >= _FAST_IMPROVEMENT and \
            (sellers_now is None or sellers_now <= _CROWDED_SELLERS):
        signals.append(_signal(
            FAST_MOVER, fast,
            f"BSR improved {fast:.0%} in the last {_FAST_WINDOW_DAYS} days"
            + (f" with {int(sellers_now)} sellers on the listing" if sellers_now else "")))

    # 02 Steady Climber. Consistency is required, not preferred -- without it this fires
    # on every fast mover whose window happens to fall inside six months.
    consistency = _consistency(bsr, _STEADY_WINDOW_DAYS)
    if steady is not None and steady >= _STEADY_IMPROVEMENT and \
            consistency is not None and consistency >= _STEADY_CONSISTENCY and \
            (price_move is None or abs(price_move) <= _PRICE_STABLE):
        signals.append(_signal(
            STEADY_CLIMBER, steady,
            f"BSR improved {steady:.0%} over ~6 months, {consistency:.0%} of steps "
            "improving, price flat"))

    # 03 Price Dip. Conditional on the rank NOT having given way: a price falling under a
    # rank that is also falling away is a listing being discounted into decline, which is
    # the opposite of an entry signal.
    rank_held = fast is None or fast > -_PRICE_STABLE
    if dip is not None and dip >= _DIP_DROP and rank_held:
        signals.append(_signal(
            PRICE_DIP, dip,
            f"Buy box price fell {dip:.0%} in {_DIP_WINDOW_DAYS} days while BSR held"))

    # 04 Crowding In. Two ways to be crowded: the count jumped, or it is simply high.
    crowd_jump = (sellers_then and sellers_now and
                  sellers_now >= sellers_then * _CROWD_RATIO and
                  sellers_now - sellers_then >= _CROWD_ABSOLUTE)
    rank_not_improving = fast is None or fast < 0.10
    if crowd_jump and rank_not_improving:
        signals.append(_signal(
            CROWDING_IN, (sellers_now - sellers_then) / float(sellers_then),
            f"Sellers went {int(sellers_then)} -> {int(sellers_now)} in "
            f"{_FAST_WINDOW_DAYS} days without the rank improving"))
    elif sellers_now and sellers_now > _CROWDED_SELLERS and not signals:
        signals.append(_signal(
            CROWDING_IN, 0.4,
            f"{int(sellers_now)} sellers already on the listing"))

    names = {entry["signal"] for entry in signals}
    if CROWDING_IN in names:
        verdict = AVOID
    elif names & {FAST_MOVER, PRICE_DIP}:
        verdict = ACT
    else:
        verdict = WATCH

    score = 0.0 if verdict == AVOID else max(
        (entry["strength"] for entry in signals), default=0.0)

    return {
        "signals": signals,
        "verdict": verdict,
        "score": round(score, 2),
        "reasons": [entry["detail"] for entry in signals],
    }
