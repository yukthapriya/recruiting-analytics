# Data dictionary

Grain is stated first for every table. All dates are calendar dates; all timestamps are local time with no zone.

## core.dim_requisition
One row per requisition (job opening).

| Column | Meaning |
|---|---|
| `req_id` | Requisition id (primary key) |
| `title`, `department`, `level`, `location` | What the opening is for |
| `recruiter_id` | Recruiter who owns it |
| `hiring_manager_id` | Hiring manager |
| `opened_date` | Date it opened |
| `status` | `open`, `filled` or `cancelled` |
| `closed_date` | Date it was filled or cancelled; empty while open |

## core.dim_candidate
One row per person. Candidate records with the same email after lower-casing and trimming are merged.

| Column | Meaning |
|---|---|
| `person_key` | Person id (primary key) |
| `email_normalized` | Lower-cased, trimmed email |
| `first_seen_at` | Earliest registration |
| `candidate_record_count` | How many raw candidate records belong to this person |

`core.candidate_xref` maps every raw `candidate_id` to its `person_key`.

## core.fact_application
One row per application to a requisition.

| Column | Meaning |
|---|---|
| `application_id` | Application id (primary key) |
| `req_id`, `person_key`, `source_name` | Links to the dimensions |
| `applied_at` | When the application was submitted |
| `screen_at`, `hm_screen_at`, `onsite_at`, `offer_at`, `hired_at` | When each stage was reached; empty if never reached |
| `furthest_stage_rank`, `furthest_stage` | Last stage reached (1 Applied to 6 Hired) |
| `outcome` | `Hired`, `Rejected`, `Withdrawn`, `Offer Declined` or `In Progress` |
| `outcome_at`, `outcome_reason` | When and why the application ended |
| `has_timestamp_issue` | True if a stage is dated before the stage preceding it |

## core.fact_stage_event
One row per application per stage reached.

| Column | Meaning |
|---|---|
| `application_id`, `stage_rank` | Primary key |
| `stage_name` | Applied, Recruiter Screen, Hiring Manager Screen, Onsite, Offer, Hired |
| `entered_at` | When the candidate entered the stage |
| `previous_entered_at` | When they entered the stage before it |
| `exited_at` | When they moved on or the application ended; empty if still in the stage |

## core.fact_hire
One row per hire (one per filled requisition).

| Column | Meaning |
|---|---|
| `application_id` | The application that was hired (primary key) |
| `req_id` | The requisition it filled (unique) |
| `accepted_date` | Date the offer was accepted |
| `start_date` | First day of work |
| `retained_90d` | Still employed after 90 days; empty if 90 days have not passed |

## core.fact_source_cost
One row per source per month: `month_start`, `source_name`, `spend_usd`.

## mart.application_funnel
One row per application, flattened for Tableau. Adds requisition attributes, the recruiter's name,
`applied_quarter`, a 0/1 `reached_*` flag for each stage, and `days_applied_to_hired`
(empty for non-hires and for applications with a timestamp issue).

## mart.funnel_stage_counts
One row per quarter, department, source and stage: `applications_reached`.

## mart.funnel_conversion
One row per department and stage (`department = 'All'` is company-wide).

| Column | Meaning |
|---|---|
| `reached` | Applications that reached the stage |
| `step_conversion` | `reached` divided by `reached` for the previous stage |
| `overall_conversion` | `reached` divided by applications |

## mart.time_to_fill
One row per filled requisition: `opened_date`, `filled_date`, `days_to_fill`, `filled_quarter`,
`hire_source`, `applications_received`.

## mart.time_to_fill_summary
One row per department and quarter: `requisitions_filled`, `median_days_to_fill`, `p90_days_to_fill`.

## mart.time_in_stage
One row per department and stage: `stage_exits`, `median_days`, `p90_days`.
Applications with a timestamp issue are excluded.

## mart.source_quality
One row per source.

| Column | Meaning |
|---|---|
| `applications`, `recruiter_screens`, `onsites`, `offers`, `hires` | Counts reaching each point |
| `share_of_applications`, `share_of_hires` | Share of the company total |
| `application_to_hire_rate` | Hires divided by applications |
| `screen_rate` | Recruiter screens divided by applications |
| `offer_acceptance_rate` | Accepted offers divided by accepted plus declined |
| `retention_90d_rate` | Retained hires divided by hires with a 90-day result |
| `spend_usd`, `cost_per_hire_usd` | Sourcing spend and spend per hire |
| `rank_by_hire_rate` | 1 = highest application-to-hire rate |

## mart.weekly_pipeline
One row per week: `applications`, `hires`, `applications_4wk_avg`.

## mart.open_requisition_aging
One row per open requisition: `days_open` as of 2025-12-31, `age_band`, `applications`, `in_progress`.

## dq.summary
One row per data quality check: `check_name`, `rows_affected`, `rows_checked`, `pct_affected`.
