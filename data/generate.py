"""Generate a synthetic applicant-tracking (ATS) export.

Real ATS data is private, so this project uses a seeded, fully reproducible
simulation of a hiring process. The same seed always produces the same files.

The export is deliberately messy in the ways real ATS exports are messy
(see INJECTED ISSUES below), so the SQL model and the data tests have
something real to clean and to catch.

Usage:  python -m data.generate [--seed 42] [--requisitions 800] [--out data/raw]
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

START = date(2024, 1, 1)
END = date(2025, 12, 31)
END_TS = datetime(2025, 12, 31, 23, 59, 59)

# department: (share of requisitions, mean applications per requisition, speed factor)
DEPARTMENTS = {
    "Manufacturing":    (0.26, 95, 0.75),
    "Service":          (0.16, 70, 0.85),
    "Vehicle Software": (0.12, 85, 1.30),
    "AI & Robotics":    (0.10, 110, 1.50),
    "Energy":           (0.10, 60, 1.00),
    "Supply Chain":     (0.10, 65, 1.00),
    "Finance":          (0.08, 55, 1.05),
    "People":           (0.08, 80, 1.00),
}
TITLES = {
    "Manufacturing":    ["Production Associate", "Process Technician", "Manufacturing Engineer", "Quality Engineer"],
    "Service":          ["Service Technician", "Service Advisor", "Mobile Technician", "Parts Advisor"],
    "Vehicle Software": ["Software Engineer", "Firmware Engineer", "QA Engineer", "Embedded Engineer"],
    "AI & Robotics":    ["Machine Learning Engineer", "Robotics Engineer", "Perception Engineer", "Data Engineer"],
    "Energy":           ["Field Engineer", "Electrical Engineer", "Installation Technician", "Project Coordinator"],
    "Supply Chain":     ["Buyer", "Logistics Analyst", "Supplier Quality Engineer", "Materials Planner"],
    "Finance":          ["Financial Analyst", "Accountant", "Payroll Specialist", "Tax Analyst"],
    "People":           ["Recruiter", "HR Partner", "People Analyst", "Recruiting Coordinator"],
}
# level: (share, speed factor)
LEVELS = {"Associate": (0.34, 0.85), "Mid": (0.32, 1.00), "Senior": (0.20, 1.15),
          "Staff": (0.06, 1.35), "Manager": (0.08, 1.25)}
LOCATIONS = [("Austin, TX", 0.30), ("Fremont, CA", 0.24), ("Palo Alto, CA", 0.14),
             ("Sparks, NV", 0.14), ("Buffalo, NY", 0.10), ("Remote", 0.08)]

# source: (share of applications, screen-pass multiplier, later-stage multiplier,
#          offer acceptance rate, 90-day retention rate)
SOURCES = {
    "Job Board":    (0.34, 0.55, 0.92, 0.74, 0.82),
    "Careers Site": (0.27, 0.90, 1.00, 0.80, 0.90),
    "LinkedIn":     (0.18, 1.00, 1.00, 0.78, 0.88),
    "Referral":     (0.08, 2.20, 1.15, 0.90, 0.95),
    "University":   (0.06, 1.00, 0.95, 0.83, 0.87),
    "Agency":       (0.04, 1.80, 1.05, 0.72, 0.84),
    "Internal":     (0.03, 2.50, 1.20, 0.93, 0.97),
}
# How each source is actually spelled in the raw export (canonical first).
SOURCE_LABELS = {
    "Job Board":    [("Job Board", 0.84), ("job board", 0.09), ("JobBoard", 0.07)],
    "Careers Site": [("Careers Site", 0.86), ("careers site", 0.08), ("Career Site", 0.06)],
    "LinkedIn":     [("LinkedIn", 0.85), ("linkedin", 0.08), ("Linked In", 0.07)],
    "Referral":     [("Referral", 0.80), ("Employee Referral", 0.14), ("referral", 0.06)],
    "University":   [("University", 0.88), ("Campus", 0.12)],
    "Agency":       [("Agency", 0.93), ("agency", 0.07)],
    "Internal":     [("Internal", 0.94), ("internal", 0.06)],
}

# Base pass rates between stages.
P_SCREEN, P_HM, P_ONSITE, P_OFFER = 0.22, 0.50, 0.45, 0.35
P_WITHDRAW = 0.04  # chance a candidate withdraws at each stage after applying

# INJECTED ISSUES (rates are approximate; the pipeline measures the real ones)
RATE_MISSING_SOURCE = 0.02     # application has no source recorded
RATE_DUPLICATE_PERSON = 0.03   # same person registered twice (email case / spacing)
RATE_DUPLICATE_EVENT = 0.01    # stage event exported twice
RATE_OUT_OF_ORDER = 0.005      # a stage timestamp earlier than the previous stage
RATE_ORPHAN_APPLICATION = 0.001  # application points at a requisition that does not exist


def weighted(rng: random.Random, pairs):
    values, weights = zip(*pairs)
    return rng.choices(values, weights=weights, k=1)[0]


def days(rng: random.Random, low: float, high: float, factor: float) -> timedelta:
    return timedelta(days=rng.uniform(low, high) * factor, hours=rng.uniform(0, 8))


def simulate_application(rng, applied_at, source, speed, dept):
    """Return the list of (stage, timestamp, reason) events after 'applied'."""
    _, screen_mult, later_mult, accept_rate, _ = SOURCES[source]
    onsite_penalty = 0.80 if dept == "AI & Robotics" else 1.0
    steps = [
        ("recruiter_screen", min(0.95, P_SCREEN * screen_mult), (2, 10), "not_qualified"),
        ("hm_screen",        min(0.95, P_HM * later_mult),      (3, 9),  "not_qualified"),
        ("onsite",           min(0.95, P_ONSITE * later_mult),  (5, 14), "failed_interview"),
        ("offer_extended",   min(0.95, P_OFFER * later_mult * onsite_penalty), (3, 10), "failed_interview"),
    ]
    events, t = [], applied_at
    for stage, p_pass, (lo, hi), reject_reason in steps:
        t = t + days(rng, lo, hi, speed)
        if events and rng.random() < P_WITHDRAW:
            events.append(("withdrawn", t, rng.choice(["candidate_withdrew", "accepted_other_offer"])))
            return events
        if rng.random() >= p_pass:
            events.append(("rejected", t, reject_reason))
            return events
        events.append((stage, t, ""))
    t = t + days(rng, 1, 7, 1.0)
    if rng.random() < accept_rate:
        events.append(("offer_accepted", t, ""))
    else:
        events.append(("offer_declined", t, rng.choice(["compensation", "accepted_other_offer", "location"])))
    return events


def generate(seed: int, n_reqs: int, out: Path) -> dict:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    recruiters = [(f"R{i:03d}", f"Recruiter {i:02d}") for i in range(1, 25)]
    dept_names = list(DEPARTMENTS)
    recruiter_depts = {rid: rng.sample(dept_names, 2) for rid, _ in recruiters}

    requisitions, applications, events, hires = [], [], [], []
    persons = []            # list of person ids
    person_last_req = {}
    app_seq = 0
    open_span = (END - START).days - 7    # requisitions keep opening until the last week

    for r in range(1, n_reqs + 1):
        req_id = f"REQ-{r:05d}"
        dept = weighted(rng, [(d, v[0]) for d, v in DEPARTMENTS.items()])
        level = weighted(rng, [(l, v[0]) for l, v in LEVELS.items()])
        speed = DEPARTMENTS[dept][2] * LEVELS[level][1]
        mean_apps = DEPARTMENTS[dept][1]
        opened = START + timedelta(days=rng.randint(0, open_span))
        opened_ts = datetime.combine(opened, datetime.min.time()) + timedelta(hours=9)
        eligible = [rid for rid, depts in recruiter_depts.items() if dept in depts] or [rid for rid, _ in recruiters]
        recruiter_id = rng.choice(eligible)
        n_apps = max(8, int(rng.gauss(mean_apps, mean_apps * 0.35)))

        sims = []
        for _ in range(n_apps):
            applied_at = opened_ts + timedelta(days=rng.triangular(0, 60, 7), hours=rng.uniform(0, 10))
            source = weighted(rng, [(s, v[0]) for s, v in SOURCES.items()])
            sims.append((applied_at, source, simulate_application(rng, applied_at, source, speed, dept)))

        accepts = sorted(ev[1] for _, _, evs in sims for ev in evs if ev[0] == "offer_accepted")
        if accepts and accepts[0] <= END_TS:
            status, cutoff, cut_reason = "filled", accepts[0], "position_filled"
        elif opened + timedelta(days=150) < END and rng.random() < 0.85:
            # old requisitions that never produced a hire are usually cancelled
            status = "cancelled"
            cutoff = opened_ts + timedelta(days=rng.randint(60, 150))
            cut_reason = "requisition_cancelled"
        else:
            status, cutoff, cut_reason = "open", None, ""
        closed_date = cutoff.date().isoformat() if cutoff else ""

        requisitions.append([req_id, rng.choice(TITLES[dept]), dept, weighted(rng, LOCATIONS), level,
                             recruiter_id, f"HM{rng.randint(1, 140):03d}", opened.isoformat(), status, closed_date])

        for applied_at, source, evs in sims:
            if cutoff and applied_at > cutoff:
                continue                      # nobody applies after the requisition closes
            if applied_at > END_TS:
                continue
            # choose the person: 20% are people who already applied to another requisition
            if persons and rng.random() < 0.20:
                person = rng.choice(persons)
                if person_last_req.get(person) == req_id:
                    person = len(persons); persons.append(person)
            else:
                person = len(persons); persons.append(person)
            person_last_req[person] = req_id

            app_seq += 1
            app_id = f"A{app_seq:07d}"
            kept, closed_early = [], False
            for stage, ts, reason in evs:
                limit = min(cutoff, END_TS) if cutoff else END_TS
                is_fill = status == "filled" and stage == "offer_accepted" and ts == cutoff
                if ts > limit or (cutoff and ts == cutoff and not is_fill):
                    closed_early = cutoff is not None and ts >= cutoff
                    break
                kept.append((stage, ts, reason))
            if closed_early and not (kept and kept[-1][0] in ("rejected", "withdrawn", "offer_declined", "offer_accepted")):
                kept.append(("rejected", cutoff + timedelta(hours=rng.uniform(1, 6)), cut_reason))
            applications.append({"application_id": app_id, "person": person, "req_id": req_id,
                                 "source": source, "applied_at": applied_at})
            for stage, ts, reason in kept:
                events.append({"application_id": app_id, "stage": stage, "ts": ts, "reason": reason})
                if stage == "offer_accepted":
                    start = ts.date() + timedelta(days=rng.randint(14, 35))
                    if start + timedelta(days=90) <= END:
                        retained = "true" if rng.random() < SOURCES[source][4] else "false"
                    else:
                        retained = ""            # too recent to know yet
                    hires.append([app_id, start.isoformat(), retained, source, ts.date().isoformat()])

    # ---- candidates, with duplicate registrations for some people ----------
    dup_people = {p for p in persons if rng.random() < RATE_DUPLICATE_PERSON}
    cand_rows, cand_seq = [], 0
    person_ids: dict[int, list[str]] = {}
    for p in persons:
        cand_seq += 1
        cid = f"C{cand_seq:07d}"
        email = f"person{p:06d}@example.com"
        cand_rows.append([cid, email, ""])
        person_ids[p] = [cid]
        if p in dup_people:
            cand_seq += 1
            cid2 = f"C{cand_seq:07d}"
            variant = rng.choice([email.upper(), f" {email}", f"{email} ", email.replace("person", "Person")])
            cand_rows.append([cid2, variant, ""])
            person_ids[p].append(cid2)
    first_seen: dict[str, datetime] = {}
    for a in applications:
        ids = person_ids[a["person"]]
        a["candidate_id"] = ids[0] if len(ids) == 1 or rng.random() < 0.5 else ids[1]
        cid = a["candidate_id"]
        if cid not in first_seen or a["applied_at"] < first_seen[cid]:
            first_seen[cid] = a["applied_at"]
    used = set(first_seen)
    cand_rows = [[cid, email, (first_seen[cid] - timedelta(minutes=rng.randint(1, 90))).isoformat(sep=" ", timespec="seconds")]
                 for cid, email, _ in cand_rows if cid in used]

    # ---- inject export issues ------------------------------------------------
    by_app: dict[str, list[dict]] = {}
    for e in events:
        by_app.setdefault(e["application_id"], []).append(e)
    for app_id, evs in by_app.items():
        if len(evs) >= 3 and rng.random() < RATE_OUT_OF_ORDER * 4:   # only multi-stage applications qualify
            i = rng.randint(1, len(evs) - 1)
            if evs[i]["stage"] not in ("rejected", "withdrawn", "offer_declined", "offer_accepted"):
                evs[i]["ts"] = evs[i - 1]["ts"] - timedelta(days=rng.uniform(1, 3))
    event_rows, ev_seq = [], 0
    for e in events:
        copies = 2 if rng.random() < RATE_DUPLICATE_EVENT else 1
        for _ in range(copies):
            ev_seq += 1
            event_rows.append([f"E{ev_seq:08d}", e["application_id"], e["stage"],
                               e["ts"].isoformat(sep=" ", timespec="seconds"), e["reason"]])

    hired_ids = {h[0] for h in hires}
    app_rows = []
    for a in applications:
        label = "" if rng.random() < RATE_MISSING_SOURCE else weighted(rng, SOURCE_LABELS[a["source"]])
        req = a["req_id"]
        if a["application_id"] not in hired_ids and rng.random() < RATE_ORPHAN_APPLICATION:
            req = f"REQ-{rng.randint(n_reqs + 1, n_reqs + 500):05d}"      # requisition that was never exported
        app_rows.append([a["application_id"], a["candidate_id"], req, label,
                         a["applied_at"].isoformat(sep=" ", timespec="seconds")])

    # ---- sourcing spend per month ------------------------------------------------
    months, m = [], date(START.year, START.month, 1)
    while m <= END:
        months.append(m); m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    hires_by = {}
    for app_id, start, _, source, accepted in hires:
        key = (accepted[:7], source); hires_by[key] = hires_by.get(key, 0) + 1   # fees booked when the offer is accepted
    cost_rows = []
    for m in months:
        ym = m.isoformat()[:7]
        campus = 15000 if m.month in (2, 3, 9, 10) else 2000
        spend = {"Job Board": 22000, "LinkedIn": 30000, "Careers Site": 6000, "University": campus,
                 "Agency": 17100 * hires_by.get((ym, "Agency"), 0),       # 18% fee on a 95k salary
                 "Referral": 2500 * hires_by.get((ym, "Referral"), 0),    # referral bonus
                 "Internal": 0}
        for s, v in spend.items():
            cost_rows.append([m.isoformat(), s, v])

    def write(name, header, rows):
        with open(out / name, "w", newline="") as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)

    write("recruiters.csv", ["recruiter_id", "recruiter_name"], recruiters)
    write("requisitions.csv", ["req_id", "title", "department", "location", "level", "recruiter_id",
                               "hiring_manager_id", "opened_date", "status", "closed_date"], requisitions)
    write("candidates.csv", ["candidate_id", "email", "created_at"], cand_rows)
    write("applications.csv", ["application_id", "candidate_id", "req_id", "source", "applied_at"], app_rows)
    write("stage_events.csv", ["event_id", "application_id", "stage", "occurred_at", "reason"], event_rows)
    write("hires.csv", ["application_id", "start_date", "retained_90d"], [h[:3] for h in hires])
    write("source_costs.csv", ["month", "source", "spend_usd"], cost_rows)
    return {"requisitions": len(requisitions), "candidates": len(cand_rows), "applications": len(app_rows),
            "stage_events": len(event_rows), "hires": len(hires), "source_cost_rows": len(cost_rows)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--requisitions", type=int, default=800)
    ap.add_argument("--out", default="data/raw")
    args = ap.parse_args()
    counts = generate(args.seed, args.requisitions, Path(args.out))
    for k, v in counts.items():
        print(f"{k:>18}: {v:,}")


if __name__ == "__main__":
    main()
