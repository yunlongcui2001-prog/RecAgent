#!/bin/bash
input=$(cat)

pct_color() {
  local pct=$1
  if [ "$pct" -ge 70 ]; then echo "\033[31m"
  elif [ "$pct" -ge 40 ]; then echo "\033[33m"
  else echo "\033[32m"
  fi
}

PCT=$(echo "$input" | python -c "import sys,json; d=json.load(sys.stdin); print(int(d.get('context_window',{}).get('used_percentage') or 0))")
H5=$(echo "$input" | python -c "import sys,json; d=json.load(sys.stdin); v=d.get('rate_limits',{}).get('five_hour',{}).get('used_percentage'); print(int(v) if v is not None else '')" 2>/dev/null)
D7=$(echo "$input" | python -c "import sys,json; d=json.load(sys.stdin); v=d.get('rate_limits',{}).get('seven_day',{}).get('used_percentage'); print(int(v) if v is not None else '')" 2>/dev/null)

# Weekly LOC (resets every Tuesday)
LOC_FILE="$HOME/.claude/loc-stats.csv"
WEEK_START=$(python -c "from datetime import date, timedelta; t=date.today(); print(t - timedelta(days=(t.weekday()-1)%7))")
if [ -f "$LOC_FILE" ]; then
  LOC=$(awk -F',' -v w="$WEEK_START" 'NR>1 && $2>=w {s+=$4} END {printf "%d",s}' "$LOC_FILE")
else
  LOC=0
fi

R="\033[0m"
CYAN="\033[36m"

CTX_COLOR=$(pct_color "$PCT")
H5_COLOR=$([ -n "$H5" ] && pct_color "$H5" || echo "$R")
D7_COLOR=$([ -n "$D7" ] && pct_color "$D7" || echo "$R")

H5_STR=$([ -n "$H5" ] && echo "${H5_COLOR}5h:${H5}%${R}" || echo "5h:--%")
D7_STR=$([ -n "$D7" ] && echo "${D7_COLOR}7d:${D7}%${R}" || echo "7d:--%")

echo -e "${CTX_COLOR}ctx ${PCT}%${R}  ${H5_STR}  ${D7_STR}  ${CYAN}+${LOC} loc${R}"
