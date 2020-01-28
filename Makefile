SHELL:=/bin/bash

py_env:
	rm -rf .venv/
	python3 -m venv .venv; \
	( \
		source .venv/bin/activate \
		pip install --upgrade pip; \
		pip install --upgrade wheel; \
		pip install -r requirements.txt; \
	)

start_dev:
	docker-compose -f docker-compose-browser.yml up -d --build

stop_dev:
	docker-compose -f docker-compose-browser.yml down

start_prod:
	docker-compose -f docker-compose-browser.yml -f docker-compose.yml up -d --build

stop_prod:
	docker-compose -f docker-compose-browser.yml -f docker-compose.yml down