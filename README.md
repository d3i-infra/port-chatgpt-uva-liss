This data donation flow is an implementation of GabrieleBossi/vidi-port-chatgpt
it contains all unique elements from that study

New in this study:
- A rudimentary pre-donation redaction of email, phone and postal code. Check out `test_redact` to see what the redactions cover

# The data donation task

The data donation task (a fork of [Feldspar](https://github.com/eyra/feldspar)) is a front end that guides participants through the data donation steps, used in conjunction with Next.
Next is a software as a service platform developed by [Eyra](https://eyra.co/) to facilitate scientific research.

For detailed tutorials and API reference, see the [documentation site](https://d3i-infra.github.io/data-donation-task/).

### What's new in v2.0.0

The extraction architecture has been consolidated around **FlowBuilder** — a standard template for per-platform donation flows. All 10 platforms have been updated with bilingual headers, improved error handling, and deterministic file resolution. The bridge layer now supports PayloadFile, structured logging, and async donation responses.

See [CHANGELOG.md](CHANGELOG.md) for the full list of changes and [MIGRATION.md](MIGRATION.md) for upgrading downstream forks.

## Installation and local testing

### Pre-requisites

- Fork or clone this repo
- Install [Node.js](https://nodejs.org/en)
- Install [pnpm](https://pnpm.io/)
- Install [Python](https://www.python.org/)
- Install [Poetry](https://python-poetry.org/)

### Setup

```sh
pnpm install
cd packages/python && poetry install
```

### Check environment

```sh
pnpm doctor
```

### Start local dev server

```sh
pnpm start
```

Visit [`http://localhost:3000`](http://localhost:3000).

## Commands

### Development

| Command | Description |
|---|---|
| `pnpm start` | Start dev server with hot reload |
| `pnpm run build` | Full production build (Python wheel + feldspar + data-collector) |
| `pnpm doctor` | Check environment setup (13 checks) |

### Testing & Type Checking

| Command | Description |
|---|---|
| `pnpm test` | Run Python tests |
| `pnpm test:py` | Same as above |
| `pnpm test:py -- tests/test_specific.py -q` | Run specific tests |
| `pnpm typecheck:py` | Run Pyright type checker |
| `pnpm verify:py` | Run both tests + type checks |

### Releases

| Command | Description |
|---|---|
| `pnpm release` | Build single all-platform release zip |
| `pnpm release:platforms` | Build one zip per platform (for Eyra Next) |

Per-platform releases are created in `releases/<timestamp>/` with one zip per platform, each filtered via `VITE_PLATFORM`.

## Architecture

See `docs/decisions/` for architectural decision records. Key structure:

```
packages/
  python/         Python extraction scripts (per-platform)
  feldspar/       Workflow UI framework (upstream Eyra)
  data-collector/ Host app / dev server with custom UI components
```

### Platform extraction flow

Each platform (Instagram, Facebook, YouTube, etc.) has a `FlowBuilder` subclass in `packages/python/port/platforms/` that handles:

1. File prompt → participant uploads DDP zip
2. Validation → DDP category detection via `DDP_CATEGORIES`
3. Extraction → `ZipArchiveReader` reads files from cached archive inventory
4. Consent → participant reviews extracted tables
5. Donation → data sent to host platform

### Supported platforms

LinkedIn, Instagram, Facebook, YouTube, TikTok, Netflix, ChatGPT, WhatsApp, X, Chrome

## Citation

If you use this repository in your research, please cite it as follows:

```
@article{Boeschoten2023,
  doi = {10.21105/joss.05596},
  url = {https://doi.org/10.21105/joss.05596},
  year = {2023},
  publisher = {The Open Journal},
  volume = {8},
  number = {90},
  pages = {5596},
  author = {Laura Boeschoten and Niek C. de Schipper and Adriënne M. Mendrik and Emiel van der Veen and Bella Struminskaya and Heleen Janssen and Theo Araujo},
  title = {Port: A software tool for digital data donation},
  journal = {Journal of Open Source Software}
}
```

You can find the full citation details in the [`CITATION.cff`](CITATION.cff) file.
