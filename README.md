# Tokopedia Laptop Dataset Scraper

A restartable, polite, research-grade Scrapling crawler that collects and validates public Tokopedia laptop product listings into reproducible raw JSONL and processed CSV/Parquet datasets.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Start a crawl:
```bash
laptop-scraper crawl --seed-config config/seeds.yaml --crawl-dir crawl_state/tokopedia_laptop --max-items 5000
```

Export dataset:
```bash
laptop-scraper export --run-id <run-id>
```

Generate quality report:
```bash
laptop-scraper quality --run-id <run-id>
```

Inspect state:
```bash
laptop-scraper inspect --run-id <run-id>
```
