FROM grafana/grafana:latest

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/ /var/lib/grafana/dashboards/

ENV GF_UNIFIED_ALERTING_ENABLED=true
ENV GF_ALERTING_ENABLED=false
ENV GF_SMTP_ENABLED=true
ENV GF_SMTP_HOST=email-smtp.us-east-1.amazonaws.com:587
ENV GF_SMTP_FROM_ADDRESS=grafana@service-checker.dev
ENV GF_SMTP_FROM_NAME=Service Checker Alerts
