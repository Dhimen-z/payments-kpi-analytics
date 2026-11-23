.PHONY: install data report powerbi dashboard test lint all

install:
	pip install -r requirements.txt

data:
	python -m analytics.dataset

report: data
	python -m analytics.report

powerbi: data
	python -m analytics.export_powerbi

dashboard: data
	streamlit run app.py

test:
	python -m pytest -q

lint:
	ruff check .

all: data report powerbi test
