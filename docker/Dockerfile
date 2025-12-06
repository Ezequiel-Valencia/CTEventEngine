FROM python:3.14-rc-slim-bookworm
USER root

ENV GOOGLE_APPLICATION_CREDENTIALS=/app/config/adc.json
ENV CACHE_DB_PATH=/app/config

######################
## Install Packages ##
######################

RUN apt-get update
RUN apt-get -y install software-properties-common
RUN python3 -m pip install uv

##################
## Add Src Code ##
##################
ADD ./CTEventEngine/ct_event_engine /app/ct_event_engine
COPY ./CTEventEngine/pyproject.toml /app
COPY ./CTEventEngine/README.md /app
# Add local copy of CTEventScraper
COPY ./CTEventScraper /CTEventScraper


#################################
## Install Python Dependencies ##
#################################

WORKDIR /app
RUN uv sync

RUN mkdir /app/config
VOLUME /app/config


#########################################
## Making Users and Setting Permisions ##
#########################################
ARG GID=1015
ARG UID=1015
RUN groupadd --gid ${GID} eventg
RUN useradd --uid ${UID} --no-log-init --create-home --groups eventg eventscraper
RUN chown eventscraper:eventg -R /app
RUN find /app/ct_event_engine -type f -exec chmod u=rx,g=rx,o= {} +
RUN find /app/ct_event_engine -type d -exec chmod u=rx,g=rx,o=rx {} +
RUN find /app/.venv -type d -exec chmod u=rwx,g=rwx,o=rx {} +
RUN chmod u=rx,g=rx,o=rx /app/ct_event_engine


######################################
## Copy Entrypoint and Install GoSu ##
######################################

USER root
ADD ./CTEventEngine/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod u=rx,g=r,o=r /app/entrypoint.sh
RUN set -eux; \
	apt-get update; \
	apt-get install -y gosu; \
	rm -rf /var/lib/apt/lists/*; \
# verify that the binary works
	gosu nobody true
ENTRYPOINT ["/app/entrypoint.sh"]

