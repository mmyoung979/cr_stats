DC=docker-compose

init-db: ## Initialize database
	@$(DC) exec backend python ./scripts/init_db.py
	@echo "Database has been initialized"

update-cards: ## Hit the CR API and update the database
	@$(DC) exec backend python ./scripts/update_cards.py
	@echo "Most recent cards have been updated"
