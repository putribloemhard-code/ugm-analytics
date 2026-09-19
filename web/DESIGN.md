# UGM Analytics Web Design

> Source/provenance: existing Streamlit UI in this repository and existing shared assets.
> Status: proposed for the non-Streamlit public analytics migration.
> Dials: ENERGY 1 / RHYTHM 2 / MOTION 1.

## Direction

Preserve the current UGM analytics interface as a platform migration. The visual language is institutional, editorial, and data-first. No landing-page redesign, decorative dashboard filler, invented metrics, or generic product marketing sections.

## Tokens

- `--navy-900: #00214a`: navigation, hero, metric surfaces.
- `--navy-800: #052c5b`: secondary navy surface.
- `--navy-700: #0a3364`: navy gradient endpoint used by the existing dashboard.
- `--yellow-500: #ffc72c`: constrained primary action and focus accent.
- `--surface: #ffffff`: main reading canvas.
- `--surface-muted: #f4f6f9`: filter and table support surfaces.
- `--ink: #182230`: primary text.
- `--ink-muted: #536174`: secondary text, only where contrast is verified.
- `--border: #d8dee8`: structural boundaries.

Navy and yellow are retained because they are already present in the current interface and assets. Pillar colours remain semantic data encodings only.

## Layout

- Desktop keeps a persistent navy sidebar and a constrained reading canvas.
- The hero keeps the existing `hero_bg.jpg` and left-aligned content over a dark scrim.
- Summary metrics remain compact navy cards because they are existing information hierarchy, not decorative cards.
- Analytics sections keep the existing order: filters, summary, explanation, visualisation, source table, export.
- At narrow widths, the sidebar becomes a labelled filter drawer. Columns stack when content stops fitting; tables use a contained scroll region with visible column context.

## Typography and motion

Use a readable system sans stack. No monospace headings or wide-tracked uppercase labels. Motion is limited to focus, hover, drawer open/close, and loading transitions. No perpetual animation.

## Accessibility

- Every control has a visible label and keyboard path.
- Focus uses a high-contrast yellow ring on light surfaces and a light ring on navy surfaces.
- Normal text targets 4.5:1 contrast; large text and non-text boundaries target 3:1.
- Every data surface has loading, empty, and error states with text explanations.
- No content depends on colour alone.
