.PHONY: setup check test test-slow dagster seeds dbt mlflow api openapi web check-web purge-health
setup:
	uv sync --locked
	cd $$(git rev-parse --show-toplevel) && $(CURDIR)/.venv/bin/pre-commit install --config rugby-injury-risk/.pre-commit-config.yaml
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict src/
	uv run pytest --cov=rugby_risk --cov-report=term-missing --cov-fail-under=80
test:
	uv run pytest -q
test-slow:
	uv run pytest -q -m slow
dagster:
	@echo "Disponible après F05"
seeds dbt:
	@echo "Disponible après F04"
mlflow:
	@echo "Disponible après F18"
api openapi:
	@echo "Disponible après F26"
web check-web:
	@echo "Disponible après F27"
purge-health:
	@echo "Disponible après F16"
