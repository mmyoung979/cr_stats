DC=docker-compose

init: ## start from scratch
	make up
	make init-db
	make update-cards
	@echo "CR Stats successfully initialized"

up: ## start up the app
	@$(DC) --env-file .env up -d
	@echo "CR Stats is running"

init-db: ## Initialize database
	@$(DC) exec backend python ./scripts/init_db.py
	@echo "Database has been initialized"

update-cards: ## Hit the CR API and update the database
	@$(DC) exec -T backend python ./scripts/update_cards.py
	@echo "Most recent cards have been updated"
