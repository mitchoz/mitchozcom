# www.mitchoz.com: the static site served by nginx. Coolify builds this with its Dockerfile build pack.
FROM nginx:1.27-alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
# Everything not listed in .dockerignore is the site itself.
COPY . /usr/share/nginx/html
RUN rm -rf /usr/share/nginx/html/deploy

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
