DC=docker-compose

init: ## start from scratch
	make up
	make migrate
	make update-cards
	@echo "CR Stats successfully initialized"

up: ## start up the app
	@$(DC) --env-file .env up -d
	@echo "CR Stats is running"

migrate: ## Apply database migrations
	@$(DC) exec -T backend python ./scripts/migrate.py
	@echo "Migrations applied"

update-cards: ## Hit the CR API and update the database
	@$(DC) exec -T backend python ./scripts/update_cards.py
	@echo "Most recent cards have been updated"
