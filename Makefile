# Build the distributable Claude skill package (dist/anki.skill).
# The package bundles skill/anki/{SKILL.md,anki.py,.env}; .env carries the
# AnkiWeb credentials, so dist/ and *.skill are gitignored.

SKILL := anki
DIST  := dist

# Where Claude Code looks for user-level skills.
SKILLS_DIR := $(HOME)/.claude/skills
# Absolute path to this repo's skill source (single source of truth).
SKILL_SRC  := $(abspath skill/$(SKILL))

.PHONY: build clean link unlink

build: | $(DIST)
	@rm -f $(DIST)/$(SKILL).skill
	@cd skill && zip -qr ../$(DIST)/$(SKILL).skill $(SKILL) -x '*.DS_Store' '*/__pycache__/*'
	@echo "built $(DIST)/$(SKILL).skill"
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
