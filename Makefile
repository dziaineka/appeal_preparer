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
	docker-compose -f env_docker/docker-compose-services.yml up -d --build

stop_dev:
	docker-compose -f env_docker/docker-compose-services.yml down

start_prod:
	docker-compose -f env_docker/docker-compose-services.yml -f env_docker/docker-compose.yml up -d --build

stop_prod:
	docker-compose -f env_docker/docker-compose-services.yml -f env_docker/docker-compose.yml down