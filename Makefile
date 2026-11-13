.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo "🚀 Linting code: Running pre-commit"
	@uv run pre-commit run -a
	@echo "🚀 Static type checking: Running mypy"
	@uv run mypy
	@echo "🚀 Checking for obsolete dependencies: Running deptry"
# 	@uv run deptry .

.PHONY: test
test: ## Test the code with pytest
	@echo "🚀 Testing code: Running pytest"
	@uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml

.PHONY: docker_build_and_deploy
docker_build_and_deploy:
	@echo "Building docker image and deploying it to K8 registry."
	@./docker/build\ and\ deploy.sh

.PHONY: all_groups
all_groups: ## Create/update the Mobilizon groups in every scripts/mobilizon_groups/*.json (extra flags: ARGS="--dry-run --force")
	@uv run python scripts/mobilizon_group.py --batch scripts/mobilizon_groups $(ARGS)
