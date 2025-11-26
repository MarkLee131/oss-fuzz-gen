# Reports

## Experiment Report

* Reports are generated locally from the raw experiment artifacts under
  `results/`.
* You can render a static HTML report with:
  `python -m report.web -r results -b <benchmark_set> -m <model> -o results-report`.
* Reports can be viewed directly from the filesystem (`file://`) or hosted with
  `python -m report.web --serve -r results -b <benchmark_set> -m <model> -o results-report`.

## Trends Report

Historical trends can be produced entirely offline by using the locally
generated data inside `results/` and `training_data/`.

# Updating the Code

* `report/web.py` renders the static site; update templates in
  `report/templates/` when adjusting the UI.

