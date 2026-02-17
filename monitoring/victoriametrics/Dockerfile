FROM victoriametrics/victoria-metrics:latest

COPY scrape.yml /etc/victoriametrics/scrape.yml

ENTRYPOINT ["/victoria-metrics-prod"]
CMD ["-promscrape.config=/etc/victoriametrics/scrape.yml", \
    "-promscrape.config.expandEnvVars=true", \
    "-storageDataPath=/victoria-metrics-data", \
    "-httpListenAddr=:8428"]
