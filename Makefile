# Build the distributable Claude skill package (dist/anki.skill).
# The package bundles skill/anki/{SKILL.md,anki.py,.env}. The repo's .env holds
# only op:// refs; `build` resolves them with `op inject` into a private temp
# staging dir, zips that, then deletes it (rm, not rip: rip's graveyard would
# keep the plaintext). Real values exist only inside dist/anki.skill (0600,
# gitignored) - for targets without `op`, e.g. skills uploaded to claude.ai.

SKILL := anki
DIST  := dist

# Where Claude Code looks for user-level skills.
SKILLS_DIR := $(HOME)/.claude/skills
# Absolute path to this repo's skill source (single source of truth).
SKILL_SRC  := $(abspath skill/$(SKILL))

.PHONY: build clean link unlink

build: | $(DIST)
	@rm -f $(DIST)/$(SKILL).skill
	@set -eu; stage=$$(mktemp -d); trap 'rm -rf "$$stage"' EXIT INT TERM; \
	cp -R skill/$(SKILL) "$$stage/"; \
	find "$$stage" \( -name .DS_Store -o -name __pycache__ \) -prune -exec rm -rf {} +; \
	op inject --in-file skill/$(SKILL)/.env --out-file "$$stage/$(SKILL)/.env" --force >/dev/null; \
	if grep -q 'op://' "$$stage/$(SKILL)/.env"; then echo "unresolved op:// ref" >&2; exit 1; fi; \
	(umask 077; cd "$$stage" && zip -qr "$(abspath $(DIST))/$(SKILL).skill" $(SKILL))
	@echo "built $(DIST)/$(SKILL).skill (secrets injected from 1Password)"
	@unzip -l $(DIST)/$(SKILL).skill

$(DIST):
	@mkdir -p $(DIST)

clean:
	@rm -rf $(DIST)
	@echo "cleaned $(DIST)"

# Symlink the skill into ~/.claude/skills so edits go live without rebuilding.
# Idempotent: safe to re-run on a fresh Mac. Refuses to clobber a real dir.
link:
	@mkdir -p $(SKILLS_DIR)
	@if [ -e "$(SKILLS_DIR)/$(SKILL)" ] && [ ! -L "$(SKILLS_DIR)/$(SKILL)" ]; then \
		echo "refusing: $(SKILLS_DIR)/$(SKILL) exists and is not a symlink"; exit 1; \
	fi
	@ln -sfn "$(SKILL_SRC)" "$(SKILLS_DIR)/$(SKILL)"
	@echo "linked $(SKILLS_DIR)/$(SKILL) -> $(SKILL_SRC)"

unlink:
	@if [ -L "$(SKILLS_DIR)/$(SKILL)" ]; then \
		rm "$(SKILLS_DIR)/$(SKILL)"; echo "unlinked $(SKILLS_DIR)/$(SKILL)"; \
	else \
		echo "nothing to unlink ($(SKILLS_DIR)/$(SKILL) is not a symlink)"; \
	fi
