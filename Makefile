.PHONY: help install setup test run status clean sync-check sync-fix

help:
	@echo "ZRAI Lead OS - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install    - Install dependencies"
	@echo "  make setup      - Run setup verification"
	@echo ""
	@echo "Running:"
	@echo "  make status     - Check system status"
	@echo "  make dry-run    - Dry run with 10 leads"
	@echo "  make run        - Run daily pipeline"
	@echo ""
	@echo "Testing:"
	@echo "  make test       - Run all tests"
	@echo "  make test-api   - Test API connections"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      - Clean cache files"
	@echo "  make logs       - View recent logs"

install:
	pip install -r requirements.txt

setup:
	python setup.py

test:
	pytest tests/ -v

test-api:
	python test_gemini_api.py
	python test_apify_connection.py
	python test_pinecone_connection.py

status:
	python -m src.cli status

dry-run:
	python -m src.cli dry_run --limit 10

run:
	python -m src.cli run_daily

resume:
	python -m src.cli resume_failed --since "24 hours ago"

inspect:
	@read -p "Enter lead_id: " lead_id; \
	python -m src.cli inspect $$lead_id

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

logs:
	tail -n 100 logs/daily.log 2>/dev/null || echo "No logs found"

format:
	black src/ tests/
	isort src/ tests/

lint:
	flake8 src/ tests/
	mypy src/

sync-check:
	python scripts/check_railway_sync.py

sync-fix:
	python scripts/check_railway_sync.py --fix
