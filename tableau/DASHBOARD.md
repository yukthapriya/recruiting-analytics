# Building the Tableau dashboard

The CSV files in this folder are written by `make export`. Connect Tableau Public to them;
no database connection is needed.

## 1. Connect

Open Tableau Public Desktop, choose **Text file**, and add these as separate data sources:

- `funnel_stage_counts.csv`
- `time_to_fill.csv`
- `source_quality.csv`
- `time_in_stage.csv`
- `data_quality_summary.csv`

## 2. Sheets

**Hiring funnel** (`funnel_stage_counts`)
- Rows: `Stage Name`, sorted by `Stage Rank` ascending.
- Columns: `SUM(Applications Reached)`.
- Calculated field `Step Conversion`: `SUM([Applications Reached]) / LOOKUP(SUM([Applications Reached]), -1)`,
  computed along `Stage Name`. Put it on Label, formatted as a percentage.
- Filters shown to the viewer: `Department`, `Source Name`, `Applied Quarter`.

**Time to fill by department** (`time_to_fill`)
- Rows: `Department`, sorted by median descending.
- Columns: `MEDIAN(Days To Fill)`. Add `PERCENTILE(Days To Fill, 0.9)` as a reference mark.

**Time to fill trend** (`time_to_fill`)
- Columns: `Filled Quarter`. Rows: `MEDIAN(Days To Fill)`. Mark type: line. Color: `Department` (optional).

**Source quality** (`source_quality`)
- Columns: `Share Of Applications`. Rows: `Share Of Hires`. Mark: circle, labelled by `Source Name`,
  sized by `Hires`. Add a reference line where the two are equal: sources above it produce
  more hires than their share of applications.
- Second sheet: bar chart of `Cost Per Hire Usd` by `Source Name`.

**Where candidates wait** (`time_in_stage`)
- Columns: `Stage Name` (sorted by `Stage Rank`, exclude nothing). Rows: `Department`.
- Mark type: square. Color and label: `Median Days`.

**Data quality footer** (`data_quality_summary`)
- A text table of `Check Name`, `Rows Affected` and `Pct Affected`, so viewers see what was cleaned.

## 3. Dashboard

Arrange as: four number tiles on top (applications, hires, application-to-hire rate, median time to fill),
the funnel and source quality side by side, the two time-to-fill sheets below, the stage heatmap and
the data quality table at the bottom. Apply the `Department` filter to all sheets that have it.

## 4. Publish

**File > Save to Tableau Public**. Copy the link into the top of `README.md` and onto your resume.
