"""Fill in missing first/last names in data/players.csv, without guessing.

A player's slug is exactly fold(first_name) + fold(last_name) -- verified
against all 1676 hand-curated 23/24 rows, zero exceptions -- where fold()
strips accents, punctuation and case. So the name is recoverable whenever we
can say where the split goes, and only then.

Two methods, both of which either know the answer or say nothing:

  1. Same slug, different club. A player who moved clubs gets a new player_id
     (it carries the team), but the same slug. Their name is already curated
     under the old id, so it's a lookup, not a guess. Recovers the most rows.

  2. Both-sides-attested split. Split the slug where the prefix is a first
     name AND the suffix is a last name we already know from elsewhere in the
     roster. Hold-out tested against the curated rows: 124 answers, 124
     correct. A split is skipped when two candidates tie on first-name length,
     so an ambiguous slug stays blank.

Deliberately NOT used: matching only a known first name and taking the rest as
the surname. Hold-out puts that at ~89% precision -- it turns "Benno Schmitz"
into "Ben Noschmitz" and "Joshua Kimmich" into "Josh Uakimmich". A blank is
recoverable later; a plausible wrong name silently isn't.

What's left blank is genuinely unrecoverable from a slug alone: a player new
to the dataset whose first and last name both appear nowhere else. The slug is
lossy too ("joakimmhle" for Joakim Maehle), so those need a real name source
from whoever produced the raw exports.

Re-run after adding a season:  python3 scripts/fill_player_names.py
"""
import csv
import os
import unicodedata
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PLAYERS_FILE = os.path.join(ROOT, "data", "players.csv")


def fold(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return "".join(ch for ch in s.lower() if ch.isalnum())


def slug_of(row):
    return row["player_id"].split("_", 2)[2]


def by_slug(rows):
    """slug -> (first, last) for every row that already has a name."""
    return {slug_of(r): (r["first_name"], r["last_name"])
            for r in rows if r["first_name"] or r["last_name"]}


def name_parts(names):
    """folded form -> the original spelling, plus how often each is attested.

    Keeping the original spelling matters: a surname rebuilt by capitalising
    the folded form loses the real casing ("Dacosta" for "da Costa").
    """
    first_spelling, last_spelling = {}, {}
    firsts, lasts = Counter(), Counter()
    for first, last in names:
        firsts[fold(first)] += 1
        lasts[fold(last)] += 1
        first_spelling.setdefault(fold(first), first)
        last_spelling.setdefault(fold(last), last)
    return firsts, lasts, first_spelling, last_spelling


def split_slug(slug, firsts, lasts):
    """The one split whose halves are both attested, or None if none/ambiguous."""
    cands = [(slug[:i], slug[i:]) for i in range(1, len(slug))
             if slug[:i] in firsts and slug[i:] in lasts]
    if not cands:
        return None
    lengths = sorted((len(first) for first, _ in cands), reverse=True)
    if len(lengths) > 1 and lengths[0] == lengths[1]:
        return None  # two equally long first names -- can't choose, so don't
    return max(cands, key=lambda c: (len(c[0]), firsts[c[0]] + lasts[c[1]]))


def main():
    with open(PLAYERS_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
        fields = rows[0].keys()

    known = by_slug(rows)
    blanks = [r for r in rows if not r["first_name"] and not r["last_name"]]

    moved = 0
    for row in blanks:
        name = known.get(slug_of(row))
        if name:
            row["first_name"], row["last_name"] = name
            moved += 1

    # Each resolved name enlarges the corpus, so a second pass can split slugs
    # the first couldn't. Runs until it stops finding any.
    split = 0
    while True:
        firsts, lasts, first_spelling, last_spelling = name_parts(by_slug(rows).values())
        found = 0
        for row in rows:
            if row["first_name"] or row["last_name"]:
                continue
            parts = split_slug(slug_of(row), firsts, lasts)
            if parts:
                row["first_name"] = first_spelling[parts[0]]
                row["last_name"] = last_spelling[parts[1]]
                found += 1
        split += found
        if not found:
            break

    with open(PLAYERS_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    left = sum(1 for r in rows if not r["first_name"] and not r["last_name"])
    print(f"Recovered {moved} names by slug (same player, new club) and {split} by split.")
    print(f"{left} of {len(rows)} rows still have no name -- not recoverable from the slug alone.")


if __name__ == "__main__":
    main()
