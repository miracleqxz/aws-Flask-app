#!/bin/sh
# Substitute environment variables in scrape config
envsubst < /etc/victoriametrics/scrape.yml.template > /etc/victoriametrics/scrape.yml

exec /victoria-metrics-prod \
  -promscrape.config=/etc/victoriametrics/scrape.yml \
  -storageDataPath=/victoria-metrics-data \
  -httpListenAddr=:8428
