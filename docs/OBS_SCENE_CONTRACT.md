# OBS Scene Contract

## Profile

Create one OBS Profile named `T&V Display System`:

- Base canvas: `11860 x 1080`
- Output resolution: `11860 x 1080`
- Frame rate: `60 FPS`
- Renderer and adapter: whichever single GPU passes the two-GPU soak test

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
ROUTE_ACTIVE
OUT_P1
OUT_P2
OUT_P3
OUT_P4
OUT_P5
OUT_P6
OUT_P7
OUT_P8
```

### Logical scenes

The numbered logical scenes own content only. They must fill the complete canvas and must not contain projector crop, overlap, mask, or warp values.

- `04_WRAPAROUND` displays `SERVER_DESKTOP` seamlessly across the panoramic canvas.
- `06_LECTURE_SINGLE` displays `FB_04` and `FB_05` once as a centered pair over black.
- `07_LECTURE_DOUBLE` displays two slightly offset copies of that pair, for four source instances total, over black.
- `08_LECTURE_SINGLE_BACKGROUND` uses the single-pair composition over `SERVER_DESKTOP`.
- `09_LECTURE_DOUBLE_BACKGROUND` uses the repeated-pair composition over `SERVER_DESKTOP`.
- `01_EIGHT_SOURCE` is the approved fixed Multi-source mapping for all eight floor boxes.
- `05_CUSTOM` is an opaque black base with all eight `CUSTOM_SLOT_Pn` scenes nested at reset transform.

Each `CUSTOM_SLOT_Pn` scene contains `FB_01` through `FB_08`. Transform every source in a slot to the same locked logical region for projector `Pn`, leaving the rest of the canvas transparent. Enable exactly one source initially. The controller changes only item visibility, so one floor box may be enabled in multiple slots without changing any geometry.

`00_BLACK` must be an opaque full-canvas black Color Source. The other routed scenes must also be opaque across the full canvas, using a background source where necessary.

### Shared router

`ROUTE_ACTIVE` contains one nested Scene source for each numbered logical scene. Keep the source names identical to the scene names. Reset every nested source transform to the full canvas and enable only one at a time.

Lock all six nested scene items. Operators do not edit this scene.

### Calibrated outputs

Each `OUT_Pn` scene contains `ROUTE_ACTIVE`. Crop, scale, position, blend-mask layers, and any projector-specific correction belong here. Lock every calibrated item after commissioning.

Do not attach a projector-specific filter directly to the shared `ROUTE_ACTIVE` source because source filters are shared by every instance. Use an output-specific group, nested calibration scene, or mask layer inside `OUT_Pn` when a filter is required.

The controller opens each `OUT_Pn` as a source projector on its verified Windows monitor index. These scenes remain open while room modes change.

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
