# OBS Scene Contract

## Profile

Create one OBS Profile named `T&V Display System`:

- Base canvas: `11860 x 1080`
- Output resolution: `11860 x 1080`
- Frame rate: `60 FPS`
- Renderer and adapter: the GPU approved for the display server

Do not use Profiles as room modes.

## Scene collection

Create one Scene Collection named `T&V Production` with these exact names:

```text
00_BLACK
01_EIGHT_SOURCE
04_WRAPAROUND
05_CUSTOM
06_LECTURE_SINGLE
07_LECTURE_DOUBLE
08_LECTURE_SINGLE_BACKGROUND
09_LECTURE_DOUBLE_BACKGROUND
CUSTOM_SLOT_P1
CUSTOM_SLOT_P2
CUSTOM_SLOT_P3
CUSTOM_SLOT_P4
CUSTOM_SLOT_P5
CUSTOM_SLOT_P6
CUSTOM_SLOT_P7
CUSTOM_SLOT_P8
```

### Logical scenes

The numbered logical scenes own the complete Program canvas. They must fill the
11,860 x 1,080 canvas. Physical projector crop, overlap, masks, and warp belong
to the display server's blend, not OBS.

- `04_WRAPAROUND` displays `SERVER_DESKTOP` seamlessly across the panoramic canvas.
- `06_LECTURE_SINGLE` displays `FB_04` and `FB_05` once as a centered pair over black.
- `07_LECTURE_DOUBLE` displays two slightly offset copies of that pair, for four source instances total, over black.
- `08_LECTURE_SINGLE_BACKGROUND` uses the single-pair composition over `SERVER_DESKTOP`.
- `09_LECTURE_DOUBLE_BACKGROUND` uses the repeated-pair composition over `SERVER_DESKTOP`.
- `01_EIGHT_SOURCE` is the approved fixed Multi-source mapping for all eight floor boxes.
- `05_CUSTOM` is an opaque black base with all eight `CUSTOM_SLOT_Pn` scenes nested at reset transform.

Each `CUSTOM_SLOT_Pn` scene contains `FB_01` through `FB_08`. Transform every
source in a slot to the same locked logical region corresponding to physical
projector position `Pn` inside the blended canvas, leaving the rest transparent.
Enable exactly one source initially. The controller changes only item visibility,
so one floor box may appear in multiple logical regions without changing geometry.

`00_BLACK` must be an opaque full-canvas black Color Source. Every other logical
scene must also be opaque across the full canvas.

## Blended output

The application selects the requested logical scene as OBS Program. It opens one
full-screen OBS Program projector on the Windows monitor exposed by the display
server. The display server then maps that single panoramic raster across the
physical projectors and applies all seam, overlap, warp, and blend corrections.

OBS must not open independent windows for the eight physical projectors. The
eight regions in `01_EIGHT_SOURCE` and `CUSTOM_SLOT_P1` through
`CUSTOM_SLOT_P8` create the one-input-per-projector appearance inside the one
blended Program canvas.

## Source pool

Use stable, physical names for the capture inputs:

```text
FB_01
FB_02
FB_03
FB_04
FB_05
FB_06
FB_07
FB_08
SERVER_DESKTOP
```

Record capture-card port, floor-box label, expected format, and audio policy during commissioning. Never infer floor-box identity from the order returned by a capture driver.
