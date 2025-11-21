#!/bin/bash

## Usage:
##   bash report/upload_report.sh results_dir benchmark_set model
##
##   results_dir is the local directory with the experiment results.
##   benchmark_set and model help label the generated report.
##   additional_args are passed through to report.web (e.g., --with-csv)

RESULTS_DIR=$1
BENCHMARK_SET=$2
MODEL=$3
# All remaining arguments are additional args for report.web
shift 3
REPORT_ADDITIONAL_ARGS="$@"
REPORT_LABEL="${REPORT_LABEL:-}"
LOCAL_BASE_URL="${LOCAL_BASE_URL:-}"

# Sleep 5 minutes for the experiment to start.
sleep 300

if [[ $RESULTS_DIR = '' ]]
then
  echo 'This script takes the results directory as the first argument'
  exit 1
fi

# The LLM used to generate and fix fuzz targets.
if [[ $MODEL = '' ]]
then
  echo "This script needs to take LLM as the third argument."
  exit 1
fi

mkdir -p results-report

update_report() {
  # Generate the report
  if [[ -z "$LOCAL_BASE_URL" ]]; then
    BASE_URL="file://$(realpath results-report)"
  else
    BASE_URL="$LOCAL_BASE_URL"
  fi
  if [[ -n "$REPORT_LABEL" ]]; then
    echo "Generating report for ${REPORT_LABEL}"
  fi
  $PYTHON -m report.web -r "${RESULTS_DIR:?}" -b "${BENCHMARK_SET:?}" -m "$MODEL" -o results-report --base-url "$BASE_URL" $REPORT_ADDITIONAL_ARGS

  cd results-report || exit 1

  echo "Report available locally at $(realpath .)."

  cd ..

  echo "Raw results remain at $(realpath "${RESULTS_DIR}")"

  echo "Preparing training data."
  rm -rf 'training_data'

  $PYTHON -m data_prep.parse_training_data \
    --experiment-dir "${RESULTS_DIR:?}" --save-dir 'training_data'
  $PYTHON -m data_prep.parse_training_data --group \
    --experiment-dir "${RESULTS_DIR:?}" --save-dir 'training_data'
  $PYTHON -m data_prep.parse_training_data --coverage \
    --experiment-dir "${RESULTS_DIR:?}" --save-dir 'training_data'
  $PYTHON -m data_prep.parse_training_data --coverage --group \
    --experiment-dir "${RESULTS_DIR:?}" --save-dir 'training_data'

  echo "Training data saved locally at $(realpath training_data)."
}

while [[ ! -f /experiment_ended ]]; do
  update_report
  echo "Experiment is running..."
  sleep 600
done

echo "Experiment finished."
update_report
echo "Final report generated locally."

