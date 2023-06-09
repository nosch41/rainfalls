.PHONY: client
client: # should be called before building frontend
	npm i; npm run generate-client

.PHONY: build
build:
	make client
	docker-compose build

.PHONY: test
test:
	PYTHONPATH=./backend/app pytest -s -vv

.PHONY: run
run:
	docker-compose up

.PHONY: run-local
run-local:
	make run-backend-local & make run-frontend-local

.PHONY: run-backend-local
run-backend-local:
	python -m uvicorn main:app --reload --app-dir backend/app/ --port 8080

.PHONY: run-frontend-local
run-frontend-local:
	make client; npm run frontend
