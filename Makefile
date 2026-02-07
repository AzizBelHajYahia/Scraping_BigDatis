# Bigdatis Scraper - Makefile
# Automation for virtual environment setup and scraping tasks

# Variables
VENV_DIR = venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip
PYTHON_VERSION = python3

# Output directory for CSV files
OUTPUT_DIR = data
LOGS_DIR = logs

# Colors for terminal output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

.PHONY: help setup install clean scrape-all scrape-residential scrape-bureaux scrape-commercial scrape-immeubles scrape-terrains test list-data clean-data archive logs interactive organize status quickstart

# Default target
help:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║         🏠 BIGDATIS SCRAPER - MAKEFILE COMMANDS              ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)📦 SETUP & INSTALLATION:$(NC)"
	@echo "  make setup              - Create venv and install dependencies"
	@echo "  make install            - Install/update dependencies only"
	@echo "  make clean              - Remove venv and cache files"
	@echo ""
	@echo "$(GREEN)🚀 SCRAPING COMMANDS:$(NC)"
	@echo "  make scrape-all         - Run ALL scrapers (automated)"
	@echo "  make scrape-residential - Scrape residential properties"
	@echo "  make scrape-bureaux     - Scrape offices"
	@echo "  make scrape-commercial  - Scrape commercial & industrial"
	@echo "  make scrape-immeubles   - Scrape buildings"
	@echo "  make scrape-terrains    - Scrape lands"
	@echo "  make interactive        - Run in interactive mode"
	@echo ""
	@echo "$(GREEN)📊 DATA MANAGEMENT:$(NC)"
	@echo "  make list-data          - List all scraped CSV files"
	@echo "  make clean-data         - Remove all CSV files"
	@echo "  make archive            - Archive all CSV files to zip"
	@echo "  make organize           - Organize CSVs into dated folders"
	@echo ""
	@echo "$(GREEN)🔧 UTILITIES:$(NC)"
	@echo "  make test               - Test all scrapers (dry run)"
	@echo "  make logs               - Show recent logs"
	@echo "  make status             - Check system status"
	@echo ""

# Create virtual environment and install dependencies
setup:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "$(BLUE)📦 Creating virtual environment...$(NC)"; \
		$(PYTHON_VERSION) -m venv $(VENV_DIR); \
		echo "$(BLUE)📥 Installing dependencies...$(NC)"; \
		$(PIP) install --upgrade pip; \
		$(PIP) install -r requirements.txt; \
		mkdir -p $(OUTPUT_DIR) $(LOGS_DIR); \
		echo "$(GREEN)✅ Virtual environment created successfully$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  Virtual environment already exists$(NC)"; \
	fi
	@echo "$(GREEN)✅ Setup complete! Virtual environment ready.$(NC)"
	@echo "$(YELLOW)💡 Run 'make scrape-all' to start scraping$(NC)"

# Install/update dependencies only
install:
	@echo "$(BLUE)📥 Installing/updating dependencies...$(NC)"
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "$(BLUE)📦 Creating virtual environment first...$(NC)"; \
		$(PYTHON_VERSION) -m venv $(VENV_DIR); \
	fi
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Dependencies updated$(NC)"

# Run all scrapers automatically
scrape-all: setup
	@echo "$(BLUE)⚡ Running ALL scrapers...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@echo "$(BLUE)🏘️  Scraping residential...$(NC)"
	@$(PYTHON) bigdatis_residential_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_residential_$(shell date +%Y%m%d_%H%M%S).log
	@echo "$(BLUE)🏢 Scraping bureaux...$(NC)"
	@$(PYTHON) bigdatis_bureaux_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_bureaux_$(shell date +%Y%m%d_%H%M%S).log
	@echo "$(BLUE)🏭 Scraping commercial...$(NC)"
	@$(PYTHON) bigdatis_commercial_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_commercial_$(shell date +%Y%m%d_%H%M%S).log
	@echo "$(BLUE)🏢 Scraping immeubles...$(NC)"
	@$(PYTHON) bigdatis_immeubles_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_immeubles_$(shell date +%Y%m%d_%H%M%S).log
	@echo "$(BLUE)🌾 Scraping terrains...$(NC)"
	@$(PYTHON) bigdatis_terrin_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_terrains_$(shell date +%Y%m%d_%H%M%S).log
	@echo "$(GREEN)✅ All scrapers completed!$(NC)"
	@make organize

# Run specific scrapers
scrape-residential: setup
	@echo "$(BLUE)🏘️ Scraping residential properties...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@$(PYTHON) bigdatis_residential_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_residential_$(shell date +%Y%m%d_%H%M%S).log
	@make organize

scrape-bureaux: setup
	@echo "$(BLUE)🏢 Scraping offices...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@$(PYTHON) bigdatis_bureaux_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_bureaux_$(shell date +%Y%m%d_%H%M%S).log
	@make organize

scrape-commercial: setup
	@echo "$(BLUE)🏭 Scraping commercial & industrial...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@$(PYTHON) bigdatis_commercial_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_commercial_$(shell date +%Y%m%d_%H%M%S).log
	@make organize

scrape-immeubles: setup
	@echo "$(BLUE)🏢 Scraping buildings...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@$(PYTHON) bigdatis_immeubles_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_immeubles_$(shell date +%Y%m%d_%H%M%S).log
	@make organize

scrape-terrains: setup
	@echo "$(BLUE)🌾 Scraping lands...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@$(PYTHON) bigdatis_terrin_scraper.py 2>&1 | tee $(LOGS_DIR)/scrape_terrains_$(shell date +%Y%m%d_%H%M%S).log
	@make organize

# Interactive mode
interactive: setup
	@echo "$(BLUE)🎯 Starting interactive mode...$(NC)"
	@mkdir -p $(OUTPUT_DIR) $(LOGS_DIR)
	@echo ""
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║              📋 BIGDATIS SCRAPER - SELECT ONE               ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo "$(GREEN)1. 🏘️  Residential (Apartments, Houses, Villas, Duplex)$(NC)"
	@echo "$(GREEN)2. 🏢 Bureaux (Offices)$(NC)"
	@echo "$(GREEN)3. 🏭 Commercial & Industrial$(NC)"
	@echo "$(GREEN)4. 🏢 Immeubles (Buildings)$(NC)"
	@echo "$(GREEN)5. 🌾 Terrains (Land)$(NC)"
	@echo "$(GREEN)6. ⚡ ALL scrapers$(NC)"
	@echo ""
	@read -p "$(YELLOW)Enter choice (1-6) [1]: $(NC)" choice; \
	case "$${choice:-1}" in \
		1) $(PYTHON) bigdatis_residential_scraper.py;; \
		2) $(PYTHON) bigdatis_bureaux_scraper.py;; \
		3) $(PYTHON) bigdatis_commercial_scraper.py;; \
		4) $(PYTHON) bigdatis_immeubles_scraper.py;; \
		5) $(PYTHON) bigdatis_terrin_scraper.py;; \
		6) make scrape-all;; \
		*) echo "$(RED)Invalid choice$(NC)";; \
	esac
	@make organize

# List all CSV files
list-data:
	@echo "$(BLUE)📊 Scraped CSV files:$(NC)"
	@if [ -d "$(OUTPUT_DIR)" ]; then \
		find $(OUTPUT_DIR) -name "*.csv" -exec ls -lh {} \; | awk '{printf "  📄 %-50s %8s %s %s %s\n", $$9, $$5, $$6, $$7, $$8}'; \
	fi
	@find . -maxdepth 1 -name "bigdatis_*.csv" -exec ls -lh {} \; | awk '{printf "  📄 %-50s %8s %s %s %s\n", $$9, $$5, $$6, $$7, $$8}'
	@echo ""
	@echo "$(YELLOW)Total CSV files: $$(find . -name 'bigdatis_*.csv' | wc -l)$(NC)"

# Organize CSV files into dated folders
organize:
	@echo "$(BLUE)📂 Organizing CSV files...$(NC)"
	@mkdir -p $(OUTPUT_DIR)
	@for file in bigdatis_*.csv; do \
		if [ -f "$$file" ]; then \
			date_folder=$$(echo $$file | grep -oP '\d{8}' | head -1); \
			if [ ! -z "$$date_folder" ]; then \
				mkdir -p $(OUTPUT_DIR)/$$date_folder; \
				mv "$$file" $(OUTPUT_DIR)/$$date_folder/; \
				echo "  ✓ Moved $$file to $(OUTPUT_DIR)/$$date_folder/"; \
			fi; \
		fi; \
	done
	@echo "$(GREEN)✅ Files organized$(NC)"

# Archive all CSV files to zip
archive:
	@echo "$(BLUE)📦 Creating archive...$(NC)"
	@archive_name="bigdatis_scrape_$$(date +%Y%m%d_%H%M%S).zip"; \
	if [ -d "$(OUTPUT_DIR)" ]; then \
		zip -r $$archive_name $(OUTPUT_DIR)/*.csv 2>/dev/null || true; \
	fi; \
	find . -maxdepth 1 -name "bigdatis_*.csv" -exec zip -r $$archive_name {} + 2>/dev/null || true; \
	if [ -f $$archive_name ]; then \
		echo "$(GREEN)✅ Archive created: $$archive_name$(NC)"; \
		ls -lh $$archive_name; \
	else \
		echo "$(YELLOW)⚠️  No CSV files to archive$(NC)"; \
	fi

# Clean data files
clean-data:
	@echo "$(YELLOW)⚠️  Removing all CSV files...$(NC)"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(OUTPUT_DIR)/*.csv; \
		rm -f bigdatis_*.csv; \
		echo "$(GREEN)✅ CSV files removed$(NC)"; \
	else \
		echo "$(BLUE)Cancelled$(NC)"; \
	fi

# Clean virtual environment and cache
clean:
	@echo "$(YELLOW)🧹 Cleaning up...$(NC)"
	@rm -rf $(VENV_DIR)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

# Test scrapers
test: setup
	@echo "$(BLUE)🧪 Testing scrapers...$(NC)"
	@$(PYTHON) -c "from bigdatis_residential_scraper import BigdatisLoopScraper; print('✅ Residential scraper OK')"
	@$(PYTHON) -c "from bigdatis_bureaux_scraper import BigdatisBureauxScraper; print('✅ Bureaux scraper OK')"
	@$(PYTHON) -c "from bigdatis_commercial_scraper import BigdatisCommercialScraper; print('✅ Commercial scraper OK')"
	@$(PYTHON) -c "from bigdatis_immeubles_scraper import BigdatisImmeublescraper; print('✅ Immeubles scraper OK')"
	@$(PYTHON) -c "from bigdatis_terrin_scraper import BigdatisTerrainscraper; print('✅ Terrains scraper OK')"
	@echo "$(GREEN)✅ All tests passed!$(NC)"

# Show recent logs
logs:
	@echo "$(BLUE)📜 Recent logs (last 50 lines):$(NC)"
	@if [ -d "$(LOGS_DIR)" ]; then \
		latest_log=$$(ls -t $(LOGS_DIR)/*.log 2>/dev/null | head -1); \
		if [ ! -z "$$latest_log" ]; then \
			echo "$(YELLOW)File: $$latest_log$(NC)"; \
			tail -50 $$latest_log; \
		else \
			echo "$(YELLOW)No logs found$(NC)"; \
		fi; \
	else \
		echo "$(YELLOW)No logs directory$(NC)"; \
	fi

# System status
status:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                    🔍 SYSTEM STATUS                           ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)Python version:$(NC)"
	@$(PYTHON_VERSION) --version || echo "  $(RED)❌ Python not found$(NC)"
	@echo ""
	@echo "$(GREEN)Virtual environment:$(NC)"
	@if [ -d "$(VENV_DIR)" ]; then \
		echo "  ✅ Active at $(VENV_DIR)"; \
		$(PYTHON) --version; \
	else \
		echo "  $(YELLOW)⚠️  Not created - run 'make setup'$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)Dependencies:$(NC)"
	@if [ -d "$(VENV_DIR)" ]; then \
		$(PIP) list | grep -E "(pandas|requests|beautifulsoup4|selenium)" || echo "  $(YELLOW)Not all installed$(NC)"; \
	else \
		echo "  $(YELLOW)⚠️  Venv not created$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)Data files:$(NC)"
	@csv_count=$$(find . -name 'bigdatis_*.csv' 2>/dev/null | wc -l); \
	echo "  📊 CSV files: $$csv_count"
	@echo ""
	@echo "$(GREEN)Disk usage:$(NC)"
	@du -sh $(OUTPUT_DIR) 2>/dev/null || echo "  📂 No data directory"
	@echo ""

# Quick start - setup and run all
quickstart: setup scrape-all
	@echo "$(GREEN)🎉 Quickstart complete!$(NC)"
