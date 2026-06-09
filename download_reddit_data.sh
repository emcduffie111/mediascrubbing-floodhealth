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
#   The "after" (-a) and "before" (-b) options are dates, but they must be
#   given as a Unix timestamp in MILLISECONDS (the number of milliseconds
#   since Jan 1, 1970). That is just how the archive's API expects dates.
#
#   The easiest way to get one: visit https://www.epochconverter.com,
#   pick your date, copy the timestamp, and add "000" to the end to turn
#   seconds into milliseconds.
#
#   Don't worry about memorizing this — when the script runs it prints the
#   date range back to you in plain English so you can confirm it's correct.
#
# REQUIREMENTS
#   - curl (pre-installed on macOS and most Linux systems)
#
# ============================================================================

# Stop immediately if any command fails, so problems are easy to spot.
set -e

# ----------------------------------------------------------------------------
# Default values — used when you don't pass the matching option on the command
# line. Edit these if you want different defaults every time you run the script.
# ----------------------------------------------------------------------------
SUBREDDIT="northcarolina"  # which subreddit to download from (no "r/" prefix)
AFTER="1727222400000"      # start of date range, in ms — Sept 24, 2024
BEFORE="1780272000000"     # end of date range, in ms   — Sept 24, 2025
TYPE="comments"            # what to download: "comments" or "posts"
LIMIT="auto"               # how many results to fetch ("auto" lets API decide)
OUTPUT_FILE=""             # file to save to; empty means print to the screen

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
    -h|--help)
      echo "Download Reddit data from arctic-shift API"
      echo ""
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -s, --subreddit SUBREDDIT    Subreddit name (default: northcarolina)"
      echo "  -a, --after TIMESTAMP        Start timestamp in ms (default: 1727222400000)"
      echo "  -b, --before TIMESTAMP       End timestamp in ms (default: 1780272000000)"
      echo "  -t, --type TYPE              Data type: comments or posts (default: comments)"
      echo "  -l, --limit LIMIT            Result limit (default: auto)"
      echo "  -o, --output FILE            Output file (default: prints to stdout)"
      echo "  -h, --help                   Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 -s AskReddit -t comments -o comments.json"
      echo "  $0 -s politics -a 1700000000000 -b 1710000000000 -t posts"
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
