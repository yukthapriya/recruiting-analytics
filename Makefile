# Default connection matches docker-compose.yml. Override with: make all DATABASE_URL=...
export DATABASE_URL ?= postgresql://postgres:postgres@localhost:5432/recruiting
PYTHON ?= python3

.PHONY: all build test export report analysis
all:        ## generate data, load, build the model, export Tableau extracts
	$(PYTHON) -m pipeline.run all
build:      ## load the raw export and rebuild every table
	$(PYTHON) -m pipeline.run build
test:       ## run the data tests
	$(PYTHON) -m pytest -q
export:     ## rewrite tableau/*.csv
	$(PYTHON) -m pipeline.run export
report:     ## print the data quality summary and headline metrics
	$(PYTHON) -m pipeline.run report
analysis:   ## run the seven analysis queries
	$(PYTHON) -m pipeline.run analysis
