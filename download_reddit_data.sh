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
# Helper: turn a date into the millisecond timestamp the API requires.
#   * "MM-DD-YYYY" (e.g. 09-24-2024) is converted to milliseconds.
#   * A value that is already all digits is treated as a ready-made timestamp
#     and passed straight through unchanged.
# Anything else is rejected with a clear error message.
# ----------------------------------------------------------------------------
to_ms() {
  local value="$1"
  if [[ "$value" =~ ^[0-9]{2}-[0-9]{2}-[0-9]{4}$ ]]; then
    # Convert MM-DD-YYYY -> seconds (macOS/BSD date), then to milliseconds. We
    # pin the time to 00:00:00 so the day always starts at midnight; otherwise
    # macOS's `date -j` fills in the current time of day.
    local seconds
    seconds=$(date -j -f "%m-%d-%Y %H:%M:%S" "$value 00:00:00" "+%s" 2>/dev/null) || {
      echo "Error: '$value' is not a valid MM-DD-YYYY date." >&2
      exit 1
    }
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
      echo "  -h, --help                   Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 -s AskReddit -t comments -o comments.json"
      echo "  $0 -s politics -a 1700000000000 -b 1710000000000 -t posts"
      echo "  $0 -s AskReddit -d data            # saves data/AskReddit_comments.json"
      echo "  $0 -s AskReddit -d data -o q1.json # saves data/q1.json"
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

# Assemble the full web address (URL) we will request, plugging in the choices
# above. "sort=asc" returns results oldest-first.
API_URL="https://arctic-shift.photon-reddit.com/api/${ENDPOINT}/search?subreddit=${SUBREDDIT}&before=${BEFORE}&limit=${LIMIT}&sort=asc&after=${AFTER}&meta-app=download-tool"

echo "Downloading ${TYPE} from r/${SUBREDDIT}..."
echo "URL: $API_URL" >&2
echo "Time range: $(date -r $((AFTER / 1000)) '+%Y-%m-%d %H:%M:%S') to $(date -r $((BEFORE / 1000)) '+%Y-%m-%d %H:%M:%S')" >&2
echo "" >&2

# Fetch the data with curl. The -H flags are HTTP headers that identify us to
# the server the same way a normal web browser would. If an output file was
# given (-o), save there; otherwise print the JSON to the screen.
if [ -n "$OUTPUT_FILE" ]; then
  curl -s "$API_URL" \
    -H "accept: */*" \
    -H "accept-language: en-US,en;q=0.9" \
    -H "referer: https://arctic-shift.photon-reddit.com/download-tool" \
    -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36" \
    -o "$OUTPUT_FILE"
  echo "Data saved to: $OUTPUT_FILE" >&2
else
  curl -s "$API_URL" \
    -H "accept: */*" \
    -H "accept-language: en-US,en;q=0.9" \
    -H "referer: https://arctic-shift.photon-reddit.com/download-tool" \
    -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
fi

echo "Done!" >&2
