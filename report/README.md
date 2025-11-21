# Reports

## Experiment Report

* `upload_report.sh` periodically (re)generates a static HTML report inside
  `results-report/` while an experiment is running.
* Reports can be viewed directly from the filesystem (`file://`) or hosted with
  `python report/web.py --serve --results-dir results --output-dir results-report`.
* Raw experiment artifacts remain under `results/` so they can be inspected or
  reprocessed locally.

## Trends Report

The previous Cloud Functions that uploaded summaries to Google Cloud Storage
have been removed. Historical trends can now be produced entirely offline by
using the locally generated data inside `results/` and `training_data/`.

# Updating the Code

* `report/web.py` renders the static site; update templates in
  `report/templates/` when adjusting the UI.
* `report/upload_report.sh` is responsible for recurring report generation and
  training-data extraction during long experiments.

