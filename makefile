
ADDITIONAL_VALID_EXTS="json|py|sh"
FINAL_DESTINATION_DIR=$(HOME)/bin/i3blocks/
IGNORE_DIRS = "templates $(STAGE_DIR)"
STAGE_DIR = staged-blocklets.tmp


default: deploy

all: clean deploy

create_stage_dir:
	mkdir -p $(STAGE_DIR)

stage: create_stage_dir
	addValidExts=$(ADDITIONAL_VALID_EXTS) ; \
	ignoredDirs=$(IGNORE_DIRS) ; \
	for blocklet in $$(ls -l | awk '/^d/ {print $$9}') ; do \
		if echo "$$ignoredDirs" | grep "$$blocklet" > /dev/null ; then \
			echo "W: $$blocklet marked ignore. Ignoring." ; \
		else \
			for aFile in $$(ls "$$blocklet" | grep -oE "$$blocklet(\.($$addValidExts))?") ; do \
				cp -uvt "$(STAGE_DIR)" "$$blocklet/$$aFile" ; \
			done \
		fi \
	done

deploy: stage
	rsync -avi --delete "$(STAGE_DIR)/" "$(FINAL_DESTINATION_DIR)"

clean:
	rm -rf $(STAGE_DIR)