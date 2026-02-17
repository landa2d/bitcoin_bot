FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY site/ /srv/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
