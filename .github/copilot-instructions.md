# AI Coding Agent Instructions for Bigdatis Scraper

## Project Overview
**Bigdatis Scraper** is a Python-based web scraping orchestrator that automates collection of real estate listings from the Bigdatis.tn API. It scrapes multiple property types across a Tunisian real estate platform, exporting data to CSV files for analysis.

## Architecture & Components

### Core Structure
- **5 Scraper Modules**: Each handles a specific property type (standalone Python scripts)
  - `bigdatis_residential_scraper.py`: Apartments, houses, villas, duplexes (4 sub-types)
  - `bigdatis_bureaux_scraper.py`: Office spaces
  - `bigdatis_commercial_scraper.py`: Commercial & industrial properties
  - `bigdatis_immeubles_scraper.py`: Buildings/immeubles
  - `bigdatis_terrin_scraper.py`: Land/terrain listings
- **Makefile**: Build automation to run scrapers with proper environment setup
- **No orchestrator**: Each scraper is run independently via Makefile

### Data Flow
1. User runs `make scrape-<type>` or `make interactive` to select a scraper
2. Makefile ensures venv is created and dependencies installed
3. Scraper script creates API payloads with filters (property type, transaction type="sale")
4. Sends POST requests to `https://server.bigdatis.tn/api/properties/search`
5. Pagination loop continues until duplicate IDs detected (deduplication via `seen_ids` set)
6. Data processed and saved to `bigdatis_<type>_YYYYMMDD_HHMM.csv` in project root
7. `make organize` moves CSV to `data/YYYYMMDD/` subdirectory for organization

### CSV Save Locations
- **Initial save**: Project root as `bigdatis_<type>_YYYYMMDD_HHMM.csv`
- **Final location**: `data/YYYYMMDD/bigdatis_<type>_YYYYMMDD_HHMM.csv` (after `make organize`)
- Clearly displayed in interactive prompts with exact path

## Key Patterns & Conventions

### Individual Scraper Implementation
Each scraper is a standalone Python script with:
```python
class BigdatisXxxxxScraper:
    def __init__(self):
        self.api_url = "https://server.bigdatis.tn/api/properties/search"
        self.headers = {...}  # Standard Mozilla headers for API auth
        self.data = []  # or self.all_data for multi-type scrapers
    
    def create_payload(self, page=1):
        # POST payload with "filter" & "propertyFilters" arrays
        # Always include transactionType="sale"
        
    def scrape_xxxxx(self):
        # Main scraping loop: paginate until seen_ids duplicates detected
        # Process each annonce via self.process_annonce()
        # Save to CSV via self.save_data()
```

### Critical Design Decisions
1. **Pagination stops on duplicate detection**: Uses `seen_ids` set to detect when API repeats same listings (more reliable than response size checks)
2. **100-item limit per request**: All payloads use `"limit": 100` for API pagination
3. **CSV-centric output**: Each property type exports its own CSV file with metadata (scraping date, page number)
4. **Headers required for API**: Standard Referer/Origin headers mandatory for API authentication
5. **Sequential execution with pauses**: 2-5 second delays between types/requests to avoid rate limiting
6. **Improved error handling**: Retry logic with exponential backoff, timeout set to 120s, clear error messages
7. **Interactive prompts**: Each scraper shows file save location and asks for confirmation before scraping

### Running Scraping Tasks
- **Setup venv**: `make setup` creates venv and installs dependencies
- **Run all scrapers**: `make scrape-all` (sequential with pauses)
- **Interactive menu**: `make interactive` (choose specific scraper)
- **Specific scrapers**: `make scrape-residential`, `make scrape-bureaux`, etc.
- **Data management**: `make list-data`, `make organize`, `make archive`, `make clean-data`

### Data Management Commands
- `make list-data` - Show all CSV files
- `make organize` - Move CSVs to `data/YYYYMMDD/` folders
- `make archive` - Create zip of all CSVs
- `make clean-data` - Delete all CSV files (prompts for confirmation)

## Dependencies
- **pandas**: DataFrame operations for data export
- **beautifulsoup4**: HTML parsing (if used by specific scrapers)
- **requests**: HTTP requests to API
- **selenium + webdriver-manager**: Browser automation (fallback for JS-heavy content)

## Common Development Tasks

### Adding a New Property Type Scraper
1. Create `bigdatis_xxxxx_scraper.py` following the pattern from existing scrapers
2. Implement scraper's main method (e.g., `scrape_xxxxx()`)
3. Add corresponding `make scrape-xxxxx` target in `Makefile`
4. Update `.github/copilot-instructions.md` with new type

### Debugging Scraping Issues
- **API timeout**: Increase timeout value in `requests.post()` call (currently 120s)
- **Check API response structure**: Verify `create_payload()` propertyFilters syntax in browser DevTools
- **Monitor pagination**: Pagination output shows page numbers and duplicate detection
- **Verify headers**: User-Agent, Origin, and Referer are mandatory for API authentication
- **Test connection**: Run `python -c "import requests; requests.post(...)"` with sample payload

### Modifying CSV Output Format
- Look for `process_annonce()` method in scraper class to adjust field mapping
- Modify columns in DataFrame before `save_to_csv()` call
- Ensure metadata fields (date, page, scraped_at) are appended consistently

## File Locations & Key Methods
| File | Key Method | Purpose |
|------|-----------|---------|
| `bigdatis_*_scraper.py` | `scrape_xxxxx()` | Main scraping entry point |
| `bigdatis_*_scraper.py` | `create_payload()` | Build POST request payload |
| `bigdatis_*_scraper.py` | `process_annonce()` | Transform raw API data to CSV row |
| `bigdatis_*_scraper.py` | `save_data()` | Save DataFrame to CSV with stats |
| `Makefile` | Multiple targets | CLI commands for setup & execution |

## Important Notes for AI Agents
- **No main.py orchestrator**: Each scraper runs independently; main.py was removed as unnecessary
- **API rate limiting**: If scraping fails, check API server availability first (may be timing out)
- **French naming convention**: Property types use French names (résidentiel, bureaux, immeubles, terrains) - maintain consistency in logs & error messages
- **Deduplication is critical**: Always implement `seen_ids` set to avoid infinite loops on paginated API responses
- **Status reporting required**: Include emoji-prefixed console output (✅, ❌, 📡, etc.) for transparency
- **Interactive prompts**: Show file save location explicitly to users so they know where to find CSV files
- **CSV files are moved by organize**: Initial save to root, then moved to `data/YYYYMMDD/` by `make organize`

