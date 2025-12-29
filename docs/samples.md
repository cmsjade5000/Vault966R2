# Preparing CSV Data (archived importer)

Before running the importer, sanitize your data so the first row is the header and titles/years are standardized.

## Quick Start

```bash
python scripts/prepare_import_csv.py --input raw_movies.csv --output data/cleaned_movies.csv
```

The script will:
- remove leading garbage rows so the first row contains `title,year,...`
- strip parenthetical descriptors from titles (`Dirty Harry (Unrated)` → `Dirty Harry`)
- collapse extra whitespace
- coerce `year` values to four-digit integers when possible
- emit a summary at `data/prepare_summary_<name>.csv`

## Checklist for Manual Files
- Ensure you have at least `title` and `year` columns (case-sensitive).
- Remove preface text like `Table 1` or Excel export metadata.
- Keep one movie per row; multi-line cells will be skipped.
- Optional columns (`genres`, `moods`, `runtime`, etc.) may be included.

## Example

Input (`scripts/samples/vault966_titles_years.csv`):
```
Table 1
title,year
Dirty Harry (Unrated),1971
```

After running `scripts/prepare_import_csv.py`:
```
title,year
Dirty Harry,1971
```

You can now feed `data/cleaned_titles.csv` into the importer:
The legacy importer now lives in `legacy/etl/`. To run it:

```bash
python legacy/etl/etl_seed.py --path data/cleaned_titles.csv
```
