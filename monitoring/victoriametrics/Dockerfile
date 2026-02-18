FROM victoriametrics/victoria-metrics:latest

RUN apk add --no-cache gettext

COPY scrape.yml /etc/victoriametrics/scrape.yml.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
