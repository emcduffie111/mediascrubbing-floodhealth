#!/bin/bash
#
# ============================================================================
# download_reddit_data.sh
# ============================================================================
#
# WHAT THIS DOES
#   Downloads Reddit comments or posts from a subreddit using the free
#   "arctic-shift" archive (https://arctic-shift.photon-reddit.com). The data
#   comes back as JSON, which you can print to the screen or save to a file.
#
# QUICK START
#   1. Make the script runnable (only needs to be done once):
#          chmod +x download_reddit_data.sh
#   2. Run it. With no options it downloads comments from r/northcarolina:
#          ./download_reddit_data.sh
#   3. To save the result to a file instead of printing it:
#          ./download_reddit_data.sh -o my_data.json
#
# COMMON EXAMPLES
#   Download comments from r/AskReddit and save them:
#       ./download_reddit_data.sh -s AskReddit -t comments -o comments.json
#
#   Download posts from r/politics for a specific date range:
#       ./download_reddit_data.sh -s politics -t posts -a 1700000000000 -b 1710000000000
#
#   See every available option:
#       ./download_reddit_data.sh --help
#
# A NOTE ON DATES (-a / -b)
#   The "after" (-a) and "before" (-b) options accept either format:
#
#     * A normal calendar date as MM-DD-YYYY, e.g.  -a 09-24-2024
#       (this is the easy one — just type the month, day, and year.)
#
#     * A Unix timestamp in MILLISECONDS, e.g.      -a 1727222400000
#       (only needed if you already have one; the script converts the
#        MM-DD-YYYY form into this automatically.)
#
#   When the script runs it prints the date range back to you in plain
#   English so you can confirm it picked the right dates.
#
# REQUIREMENTS
#   - curl (pre-installed on macOS and most Linux systems)
#
# ============================================================================

# Stop immediately if any command fails, so problems are easy to spot.
set -e

# ----------------------------------------------------------------------------
# Linux and macOS ship two different `date` commands that take different flags.
# Detect which one we have once, so the helpers below can use the right syntax.
#   * GNU date (Linux):  has --version, converts with  date -d "..."
#   * BSD date (macOS):  no --version, converts with   date -j -f "..."
# ----------------------------------------------------------------------------
if date --version >/dev/null 2>&1; then
  DATE_FLAVOR="gnu"
else
  DATE_FLAVOR="bsd"
fi

# Helper: convert a Unix timestamp in SECONDS into a human-readable date string.
seconds_to_human() {
  if [[ "$DATE_FLAVOR" == "gnu" ]]; then
    date -d "@$1" '+%Y-%m-%d %H:%M:%S'
  else
    date -r "$1" '+%Y-%m-%d %H:%M:%S'
  fi
}

# ----------------------------------------------------------------------------
# Helper: turn a date into the millisecond timestamp the API requires.
#   * "MM-DD-YYYY" (e.g. 09-24-2024) is converted to milliseconds.
#   * A value that is already all digits is treated as a ready-made timestamp
#     and passed straight through unchanged.
# Anything else is rejected with a clear error message.
# ----------------------------------------------------------------------------
to_ms() {
  local value="$1"
  if [[ "$value" =~ ^([0-9]{2})-([0-9]{2})-([0-9]{4})$ ]]; then
    # Split MM-DD-YYYY into its parts so we can rebuild it in the YYYY-MM-DD
    # form both `date` versions understand. We pin the time to 00:00:00 so the
    # day always starts at midnight (otherwise macOS fills in the current time).
    local mm="${BASH_REMATCH[1]}" dd="${BASH_REMATCH[2]}" yyyy="${BASH_REMATCH[3]}"
    local iso="${yyyy}-${mm}-${dd} 00:00:00"
    local seconds
    if [[ "$DATE_FLAVOR" == "gnu" ]]; then
      seconds=$(date -d "$iso" "+%s" 2>/dev/null)
    else
      seconds=$(date -j -f "%Y-%m-%d %H:%M:%S" "$iso" "+%s" 2>/dev/null)
    fi
    if [[ -z "$seconds" ]]; then
      echo "Error: '$value' is not a valid MM-DD-YYYY date." >&2
      exit 1
    fi
    echo "$((seconds * 1000))"
  elif [[ "$value" =~ ^[0-9]+$ ]]; then
    # Already a millisecond timestamp.
    echo "$value"
  else
    echo "Error: date '$value' must be MM-DD-YYYY (e.g. 09-24-2024) or a ms timestamp." >&2
    exit 1
  fi
}

# ----------------------------------------------------------------------------
# Default values — used when you don't pass the matching option on the command
# line. Edit these if you want different defaults every time you run the script.
# ----------------------------------------------------------------------------
SUBREDDIT="northcarolina"  # which subreddit to download from (no "r/" prefix)
AFTER="09-24-2024"         # start of date range (MM-DD-YYYY or a ms timestamp)
BEFORE="09-24-2025"        # end of date range   (MM-DD-YYYY or a ms timestamp)
TYPE="comments"            # what to download: "comments" or "posts"
LIMIT="auto"               # how many results to fetch ("auto" lets API decide)
OUTPUT_FILE=""             # file name to save to; empty means print to the screen
DIRECTORY=""               # folder to save into; created automatically if missing
PAGINATE=false             # if true, keep fetching until the WHOLE range is downloaded

# Headers that make our request look like a normal web browser to the server.
# Stored in one array so every curl call below uses the exact same set.
CURL_HEADERS=(
  -H "accept: */*"
  -H "accept-language: en-US,en;q=0.9"
  -H "referer: https://arctic-shift.photon-reddit.com/download-tool"
  -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

# ----------------------------------------------------------------------------
# Read the options the user typed (e.g. -s AskReddit). Each option below has a
# short form (-s) and a long form (--subreddit); both do the same thing.
# ----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    -s|--subreddit)
      SUBREDDIT="$2"
      shift 2
      ;;
    -a|--after)
      AFTER="$2"
      shift 2
      ;;
    -b|--before)
      BEFORE="$2"
      shift 2
      ;;
    -t|--type)
      TYPE="$2"
      shift 2
      ;;
    -l|--limit)
      LIMIT="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -d|--directory)
      DIRECTORY="$2"
      shift 2
      ;;
    -A|--all)
      PAGINATE=true
      shift
      ;;
    -h|--help)
      echo "Download Reddit data from arctic-shift API"
      echo ""
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -s, --subreddit SUBREDDIT    Subreddit name (default: northcarolina)"
      echo "  -a, --after DATE             Start date as MM-DD-YYYY or ms (default: 09-24-2024)"
      echo "  -b, --before DATE            End date as MM-DD-YYYY or ms (default: 09-24-2025)"
      echo "  -t, --type TYPE              Data type: comments or posts (default: comments)"
      echo "  -l, --limit LIMIT            Result limit (default: auto)"
      echo "  -o, --output FILE            Output file name (default: prints to stdout)"
      echo "  -d, --directory DIR          Folder to save into; created if missing."
      echo "                               Auto-names the file if -o is not given."
      echo "  -A, --all                    Download EVERYTHING in the date range by"
      echo "                               paginating (the API caps a single request"
      echo "                               at 1000 items). Requires 'jq'."
      echo "  -h, --help                   Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 -s AskReddit -t comments -o comments.json"
      echo "  $0 -s politics -a 12-01-2025 -b 05-01-2026 -t posts"
      echo "  $0 -s AskReddit -d data            # saves data/AskReddit_comments.json"
      echo "  $0 -s AskReddit -d data -o q1.json # saves data/q1.json"
      echo "  $0 -s AskReddit --all -d data      # fetch the COMPLETE range, not just 1000"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use -h or --help for usage information"
      exit 1
      ;;
  esac
done

# Make sure the user asked for something the API understands.
if [[ "$TYPE" != "comments" && "$TYPE" != "posts" ]]; then
  echo "Error: Type must be 'comments' or 'posts', got: $TYPE"
  exit 1
fi

# Convert the date options into the millisecond timestamps the API needs. This
# accepts either MM-DD-YYYY or an existing ms timestamp (see to_ms above).
AFTER=$(to_ms "$AFTER")
BEFORE=$(to_ms "$BEFORE")

# ----------------------------------------------------------------------------
# Work out where to save the file, based on -o (file name) and -d (directory).
#   * If a directory was given, create it (and any parent folders) if needed.
#   * If no file name was given but a directory was, auto-name the file using
#     the subreddit and type, e.g. "AskReddit_comments.json".
#   * We only keep the file name part of -o (basename), so the -d folder always
#     decides the location and the two can't disagree.
# The result is stored back in OUTPUT_FILE, which the curl step below uses.
# ----------------------------------------------------------------------------
if [ -n "$DIRECTORY" ]; then
  mkdir -p "$DIRECTORY"
  if [ -n "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="${DIRECTORY%/}/$(basename "$OUTPUT_FILE")"
  else
    OUTPUT_FILE="${DIRECTORY%/}/${SUBREDDIT}_${TYPE}.json"
  fi
fi

# The API has a separate address ("endpoint") for comments vs posts, which
# happens to match the type name exactly.
ENDPOINT="$TYPE"
API_BASE="https://arctic-shift.photon-reddit.com/api/${ENDPOINT}/search"

# Helper: fetch ONE batch. Takes the "after" cursor (in ms) as its argument and
# prints the raw JSON response. "sort=asc" returns results oldest-first.
fetch_batch() {
  local after_cursor="$1"
  local url="${API_BASE}?subreddit=${SUBREDDIT}&before=${BEFORE}&limit=${LIMIT}&sort=asc&after=${after_cursor}&meta-app=download-tool"
  curl -s "$url" "${CURL_HEADERS[@]}"
}

echo "Downloading ${TYPE} from r/${SUBREDDIT}..." >&2
echo "Time range: $(seconds_to_human $((AFTER / 1000))) to $(seconds_to_human $((BEFORE / 1000)))" >&2
echo "" >&2

# Helper: send the finished JSON to the chosen destination (file or screen).
emit_result() {
  if [ -n "$OUTPUT_FILE" ]; then
    cat > "$OUTPUT_FILE"
    echo "Data saved to: $OUTPUT_FILE" >&2
  else
    cat
  fi
}

if [ "$PAGINATE" != "true" ]; then
  # --------------------------------------------------------------------------
  # SIMPLE MODE (default): one request. Fast, but the API returns at most ~1000
  # items, so a busy subreddit + wide date range may be cut short. Use --all to
  # guarantee you get everything.
  # --------------------------------------------------------------------------
  fetch_batch "$AFTER" | emit_result
else
  # --------------------------------------------------------------------------
  # COMPLETE MODE (--all): page through the whole range so nothing is missed.
  #
  # How it works: results come back oldest-first. After each batch we move the
  # "after" cursor forward to the newest second we just saw, MINUS 1 millisecond.
  # Why minus 1? The API's "after" is exclusive and timestamps only have
  # one-second resolution, so if a single second's items get split across the
  # 1000-item page limit, a plain cursor would skip the leftovers. Backing up by
  # 1ms re-includes that whole second on the next page; we then de-duplicate by
  # each item's unique "id" so the overlap costs nothing. We stop once a batch
  # reveals no newer second (everything left was already seen).
  # --------------------------------------------------------------------------
  command -v jq >/dev/null 2>&1 || {
    echo "Error: --all needs the 'jq' tool to combine pages. Install it with:" >&2
    echo "         macOS:  brew install jq" >&2
    echo "         Linux:  sudo apt-get install jq   (or your package manager)" >&2
    exit 1
  }

  # Collect each page as a separate file in a temp folder, merge them at the end.
  WORK_DIR=$(mktemp -d)
  trap 'rm -rf "$WORK_DIR"' EXIT   # always clean up, even on error

  cursor="$AFTER"
  page=0
  total=0
  prev_newest=-1
  while true; do
    page=$((page + 1))
    response=$(fetch_batch "$cursor")

    # Surface API errors (e.g. bad parameters) instead of writing junk.
    err=$(echo "$response" | jq -r '.error // empty' 2>/dev/null)
    if [ -n "$err" ]; then
      echo "Error from API: $err" >&2
      exit 1
    fi

    count=$(echo "$response" | jq '.data | length')
    if [ "$count" -eq 0 ]; then
      break   # nothing left in the range
    fi

    echo "$response" | jq -c '.data[]' >> "$WORK_DIR/items.ndjson"
    total=$((total + count))
    echo "  page $page: +$count items (total fetched so far: $total, dupes removed at end)" >&2

    # Find the newest second in this batch. If it didn't advance past the last
    # batch, every item here was already seen — we've reached the end (or, in the
    # extremely rare case, one second holds more items than a single request can
    # return). Either way, stop.
    newest=$(echo "$response" | jq '[.data[].created_utc] | max')
    if [ "$newest" -le "$prev_newest" ]; then
      [ "$count" -ge 1000 ] && echo "  note: a single second holds >1000 items; a few may be uncovered." >&2
      break
    fi
    prev_newest="$newest"

    # Advance the cursor to the start of the newest second (newest*1000) minus
    # 1ms, so the next request re-includes that whole second (see note above).
    cursor=$((newest * 1000 - 1))
  done

  # Merge every page, drop duplicates by id, and restore oldest-first order.
  if [ -f "$WORK_DIR/items.ndjson" ]; then
    unique=$(jq -s 'unique_by(.id) | sort_by(.created_utc)' "$WORK_DIR/items.ndjson")
  else
    unique="[]"
  fi
  kept=$(echo "$unique" | jq 'length')
  echo "" >&2
  echo "Complete: $kept unique ${TYPE} across $page request(s)." >&2

  # Wrap back into the same {"data":[...]} shape the API uses.
  echo "$unique" | jq '{data: .}' | emit_result
fi

echo "Done!" >&2
