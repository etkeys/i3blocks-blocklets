
ADDITIONAL_VALID_EXTS="json|py|sh"
FINAL_DESTINATION_DIR=$(HOME)/bin/i3blocks/
IGNORE_DIRS = "templates $(STAGE_DIR)"
STAGE_DIR = staged-blocklets.tmp


default: stage

all: clean install

prestage:
	mkdir -p $(STAGE_DIR)

stage: prestage
	addValidExts=$(ADDITIONAL_VALID_EXTS) ; \
	ignoredDirs=$(IGNORE_DIRS) ; \
	for blocklet in $$(ls -l | awk '/^d/ {print $$9}') ; do \
		if echo "$$ignoredDirs" | grep "$$blocklet" > /dev/null ; then \
			echo "W: $$blocklet marked ignore. Ignoring." ; \
		else \
			for aFile in $$(ls "$$blocklet" | grep -oE "$$blocklet(\.($$addValidExts))?") ; do \
				cp -puvt "$(STAGE_DIR)" "$$blocklet/$$aFile" ; \
			done \
		fi \
	done

install: stage
	rsync -avi --delete "$(STAGE_DIR)/" "$(FINAL_DESTINATION_DIR)"

clean:
	rm -rf $(STAGE_DIR) > /dev/null 2>&1
