# weather_sticker.py

Generates a transparent-background PNG weather card (BBC-forecast style, matching
`merchantsyard_tdg/HUB/refs/weathercheckaa-final.png`) for Leicester, covering
Thursday / Friday / Saturday of the current week. Output is 1308x374 (2x the
reference), RGBA with transparency outside the rounded corners — drop it straight
onto an Instagram story.

## Run

```
python3 /Users/paulventura/tdg-hub/tools/weather_sticker.py
```

No pip installs needed (stdlib + Pillow, macOS system Helvetica). Fetches live
data from open-meteo (free, no API key).

## Flags

- `--venue merchants-yard` (default) or `--venue moonshine` — picks which venue
  root's WEEKS folder to save into.
- `--out /path/to/file.png` — save to an explicit path instead (venue ignored
  for the save location).

## Where output lands

By default: the newest non-archived week folder (per `week.json`'s `archived`
flag) under the venue root, in a `stories/` subfolder (created if missing):

```
<venue root>/WEEKS/<newest week>/stories/weather-sticker-<thursday YYYY-MM-DD>.png
```

e.g. `/Users/paulventura/merchantsyard_tdg/WEEKS/2026-08-17/stories/weather-sticker-2026-08-20.png`

## Behaviour notes

- Days: Thu/Fri/Sat of the current Mon–Sun week (Europe/London). On a Sunday it
  rolls forward to the next week's Thu/Fri/Sat.
- Temps are rounded to whole degrees; the script prints the fetched forecast so
  you can sanity-check it.
- Icons: sunny (weather codes 0–1), sun-behind-cloud (2), grey cloud (3+, incl.
  rain — there is no separate rain icon, matching the reference set).
