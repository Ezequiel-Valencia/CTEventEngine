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
all_groups: ctgrassroots_groups underground_groups ## Create/update the groups on both sites

.PHONY: ctgrassroots_groups
ctgrassroots_groups: ## Create/update the groups on ctgrassroots.org from scripts/mobilizon_groups/ctgrassroots/*.json (MOBILIZON_ENDPOINT; extra flags: ARGS="--dry-run --force")
	@uv run python scripts/mobilizon_group.py --batch scripts/mobilizon_groups/ctgrassroots $(ARGS)

.PHONY: underground_groups
underground_groups: ## Create/update the groups on underground.ctgrassroots.org from scripts/mobilizon_groups/underground/*.json (UNDERGROUND_MOBILIZON_ENDPOINT; extra flags: ARGS="--dry-run --force")
	@test -n "$$UNDERGROUND_MOBILIZON_ENDPOINT" || (echo "Set UNDERGROUND_MOBILIZON_ENDPOINT, e.g. https://underground.ctgrassroots.org/api" && exit 1)
	@uv run python scripts/mobilizon_group.py --batch scripts/mobilizon_groups/underground --endpoint "$$UNDERGROUND_MOBILIZON_ENDPOINT" $(ARGS)
