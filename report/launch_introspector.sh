# Default configuration
SOURCE_MODE="benchmark"
# By default, build FI DB from the whole conti-benchmark directory
BENCHMARK_SET=""
DATA_DIR="data-dir"
PORT=8080
PYTHON="${PYTHON:-python}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --source)
      SOURCE_MODE="$2"
      shift 2
      ;;
    --benchmark-set)
      BENCHMARK_SET="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --python)
      PYTHON="$2"
      shift 2
      ;;
    --help)
      grep '^#' "$0" | sed 's/^# //' | sed 's/^#//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Validate source mode
if [[ "$SOURCE_MODE" != "benchmark" && "$SOURCE_MODE" != "data-dir" ]]; then
  echo "Error: --source must be 'benchmark' or 'data-dir'"
  exit 1
fi

echo "========================================"
echo "Fuzz Introspector Launcher"
echo "========================================"
echo "Source mode: $SOURCE_MODE"
echo "Python: $PYTHON"
echo "Port: $PORT"
echo "========================================"

# Utility function: Check if port is in use
check_port() {
  if lsof -i :$PORT >/dev/null 2>&1; then
    echo "Warning: Port $PORT is already in use"
    echo "Kill existing process? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
      PID=$(lsof -t -i :$PORT 2>/dev/null)
      if [ -n "$PID" ]; then
        kill -9 $PID
        echo "Killed process $PID"
        sleep 2
      fi
    else
      echo "Exiting..."
      exit 1
    fi
  fi
}

# Utility function: Wait for server to start
wait_for_server() {
  local host=$1
  local max_attempts=30
  local attempt=0
  
  echo "Waiting for Fuzz Introspector server to start..."
  while [ $attempt -lt $max_attempts ]; do
    if curl -s http://${host}:${PORT} 2>&1 | grep -q "Fuzzing"; then
      echo "✓ Fuzz Introspector server is running at http://${host}:${PORT}"
      return 0
    fi
    attempt=$((attempt + 1))
    echo "  Attempt $attempt/$max_attempts - waiting 5 seconds..."
    sleep 5
  done
  
  echo "Error: Server failed to start after $max_attempts attempts"
  return 1
}

BASE_DIR=$PWD
check_port

# Clone and setup Fuzz Introspector
echo "Cloning Fuzz Introspector..."
if [ -d "fuzz-introspector" ]; then
  echo "  fuzz-introspector directory already exists, using existing clone"
else
  git clone --depth=1 https://github.com/ossf/fuzz-introspector
fi

cd fuzz-introspector
ROOT_FI=$PWD

# Install dependencies
echo "Installing Fuzz Introspector dependencies..."
cd tools/web-fuzzing-introspection
${PYTHON} -m pip install -q -r requirements.txt

# Mode-specific setup
if [[ "$SOURCE_MODE" == "benchmark" ]]; then
  echo "========================================"
  echo "Mode: Benchmark Source"
  if [[ -n "$BENCHMARK_SET" ]]; then
    echo "Benchmark set: $BENCHMARK_SET"
  else
    echo "Benchmark root: conti-benchmark (all benchmarks)"
  fi
  echo "========================================"
  
  # Create database from benchmark directory
  cd app/static/assets/db/
  
  BENCHMARK_ROOT="$BASE_DIR/conti-benchmark"
  if [[ -n "$BENCHMARK_SET" ]]; then
    BENCHMARK_ROOT="$BENCHMARK_ROOT/$BENCHMARK_SET"
  fi
  
  if [ ! -d "$BENCHMARK_ROOT" ]; then
    echo "Error: Benchmark directory not found: $BENCHMARK_ROOT"
    exit 1
  fi
  
  echo "Creating Fuzz Introspector database from benchmarks..."
  ${PYTHON} ./web_db_creator_from_summary.py \
      --output-dir=$PWD \
      --input-dir=$PWD \
      --base-offset=1 \
      --includes="$BENCHMARK_ROOT"
  
  # Launch server
  cd $ROOT_FI/tools/web-fuzzing-introspection/app/
  echo "Starting Fuzz Introspector server on port $PORT..."
  FUZZ_INTROSPECTOR_SHUTDOWN=1 ${PYTHON} ./main.py >> /dev/null 2>&1 &
  SERVER_PID=$!
  
  wait_for_server "0.0.0.0"
  
elif [[ "$SOURCE_MODE" == "data-dir" ]]; then
  echo "========================================"
  echo "Mode: Data Directory Source"
  echo "Data directory: $DATA_DIR"
  echo "========================================"
  
  if [ ! -d "$BASE_DIR/$DATA_DIR" ]; then
    echo "Error: Data directory not found: $BASE_DIR/$DATA_DIR"
    exit 1
  fi
  
  # Check if required subdirectories exist
  if [ ! -d "$BASE_DIR/$DATA_DIR/oss-fuzz2" ]; then
    echo "Error: $BASE_DIR/$DATA_DIR/oss-fuzz2 not found"
    exit 1
  fi
  
  if [ ! -d "$BASE_DIR/$DATA_DIR/fuzz_introspector_db" ]; then
    echo "Error: $BASE_DIR/$DATA_DIR/fuzz_introspector_db not found"
    exit 1
  fi
  
  # List projects to analyze
  echo "Projects to analyze:"
  for d in $BASE_DIR/$DATA_DIR/oss-fuzz2/projects/*; do
    if [ -d "$d" ]; then
      echo "  - $(basename $d)"
    fi
  done
  
  # Copy pre-built database
  cd $ROOT_FI/tools/web-fuzzing-introspection/app/static/assets
  rm -rf ./db
  cp -rf $BASE_DIR/$DATA_DIR/fuzz_introspector_db db
  echo "✓ Copied pre-built database from $DATA_DIR"
  
  # Launch server with local OSS-Fuzz directory
  cd $ROOT_FI/tools/web-fuzzing-introspection/app/
  echo "Starting Fuzz Introspector server on port $PORT..."
  FUZZ_INTROSPECTOR_SHUTDOWN=1 \
  FUZZ_INTROSPECTOR_LOCAL_OSS_FUZZ=$BASE_DIR/$DATA_DIR/oss-fuzz2 \
  ${PYTHON} main.py >> /dev/null 2>&1 &
  SERVER_PID=$!
  
  wait_for_server "127.0.0.1"
fi

# Return to base directory
cd $BASE_DIR

echo "========================================"
echo "✓ Setup complete!"
echo "========================================"
echo "Server PID: $SERVER_PID"
echo "API endpoint: http://127.0.0.1:${PORT}/api"
echo ""
echo "To use with LogicFuzz:"
echo "  python run_logicfuzz.py --agent -y <benchmark.yaml> \\"
echo "    --model <model-name> \\"
echo "    -e http://127.0.0.1:${PORT}/api"
echo ""
echo "To shutdown the server:"
echo "  curl http://127.0.0.1:${PORT}/api/shutdown"
echo "  # or"
echo "  kill $SERVER_PID"
echo "========================================"
echo "Waiting for Fuzz Introspector server to exit (press Ctrl+C to stop)..."

# Keep the script (and thus the Docker container) alive as long as the
# Fuzz Introspector server process is running.
wait "$SERVER_PID"

exit 0

