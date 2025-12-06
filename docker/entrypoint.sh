#!/bin/sh

#!-------------- Past User Solutions -----------------------------!#

#################
# Bad Solutions #
#################
# 1). User creation in build, then modification in entry is super slow because the layer is already baked and is being modified
#     plus it has to copy a bunch of files again. https://github.com/docker/cli/issues/3559
#
# 2). Create a user group in build that just gets added to a user created in the entry script. Had some strange permission problems

####################
# Current Solution #
####################
#
# Just have the UID and GID be build arguments for the image. If another ID is required create a new build.
# Good enough for now and still provides security. Brittle in the fact that if UID/GID changes then the image will no longer work
# but UID/GID should not be changing regularly for these files are handled by processes, not actual users.

echo "Starting Event Engine"
# Gosu https://github.com/tianon/gosu
gosu eventscraper:eventg uv run python /app/ct_event_engine/runner.py
