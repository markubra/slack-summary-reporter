IMAGE_NAME=slack-summary-reporter

.PHONY: build run

build:
	docker build -t $(IMAGE_NAME) .

run:
	docker run --rm --name $(IMAGE_NAME) --env-file .env $(IMAGE_NAME)
