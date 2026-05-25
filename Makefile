# Build the distributable Claude skill package (dist/anki.skill).
# The package bundles skill/anki/{SKILL.md,anki.py,.env}; .env carries the
# AnkiWeb credentials, so dist/ and *.skill are gitignored.

SKILL := anki
DIST  := dist

.PHONY: build clean

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
