# Instagram Stories fonts — what they actually are

Researched 23 Aug 2026. Keep this; it settles a recurring question.

## The headline finding

Instagram's own typeface is **Instagram Sans**, designed by **Colophon Foundry**
(London) with Instagram's in-house brand team, launched May 2022. It is a
"contemporary remix of grotesque and geometric styles" built around the
"squircle" from the Instagram glyph. Styles: Regular, Headline, Condensed, Script.

**It is proprietary to Meta and not licensed for public use.** Several sites
offer "free Instagram Sans downloads" — those are unauthorised copies. We do
not use them. Using it outside the platform breaches Meta's brand guidelines.

## What each Stories font option is

| IG option | What it actually is | What we use |
|---|---|---|
| Classic / default | Instagram Sans | Inter 700, or Helvetica Neue Bold |
| Modern | Aveny T | Inter / DM Sans |
| Typewriter | **Courier** (community-confirmed) | Courier New Bold — effectively exact |
| Neon | Cosmopolitan Script (close match) | n/a, we don't use it |
| Strong | Roboto (unconfirmed) | Archivo Black for heavy caps |

Sources: dafont forum thread 364721 (typewriter = Courier, modern = Aveny T),
about.instagram.com/brand/type, fontsarena, TechCrunch May 2022.

## The rule for this studio

**If the text can be typed in the Instagram app, type it in the app.**
That gives the real Instagram Sans, exactly, for free. No approximation beats it.

Only bake text into a file when the asset has to exist as a finished file
(scheduled posts, ads uploads, handovers). In that case:

- Typewriter look  -> Courier New Bold. This one genuinely matches.
- Default look     -> Inter 700 (closest legitimate match to Instagram Sans)
- Heavy caps look  -> Archivo Black
- Moonshine serif  -> Bodoni 72 (matches their Didone brand type)
- Moonshine reels  -> Playfair Display Italic (Chelsea's spec, size 10 in CapCut)

Installed and available: Inter, DM Sans, Poppins, Archivo Black, Courier New,
Bodoni 72, Playfair Display Italic, Open Sauce Sans.


## Measured matches (brute-forced against posted files, 23 Aug 2026)

**The Moonshine thin-italic line** ("When class is the dress code",
"Today at Moonshine"): posted line is a wide, hairline Didone italic.
Winner by blind judge (84/100) and metrics (width 1.03, stroke 1.02):
**Playfair variable Italic — opsz 900, wght 300, wdth 112.5, tracking ~6% of em**
(/tmp copy installed; file: Playfair-Italic[opsz,wdth,wght].ttf from google/fonts/ofl/playfair).
Runner-up: Didot Italic stretched 1.12 with tracking (width 1.00 but hairlines too thin, 74/100).
The old recipe (Playfair DISPLAY Italic, no width) reads too narrow — do not reuse.

**Merchants Yard What's On headline**: Open Sauce Sans **500** (stroke ratio 0.99
vs the posted slide). 400 and Helvetica Neue read too light, 700 too heavy.
Headline = 500, body/details = 400, emphasis = 700.

**Moonshine display caps** ("THIS WEEK"): Perandory Condensed by Kulturë Type,
uppercase only. FREE FOR PERSONAL USE ONLY — commercial licence required, so it
is deliberately not installed for client work. Ask Chelsea/Nico what licence the
Canva file uses. Until licensed: Bodoni 72 with scaleX 0.529 stays the substitute.

**Ground truth kept**: four screen recordings of real posted stories are the
reference set for IG-typed text (DJ Benzo story, Secure your dancefloor, weather
sticker, When we're open) — originally in ~/Downloads, uuid-named .MOVs.
