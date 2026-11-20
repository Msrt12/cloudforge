FROM alpine:3.23

RUN apk add --no-cache busybox-extras && \
    mkdir -p /www && \
    echo '{"status":"healthy"}' > /www/health && \
    echo 'CloudForge Application - Version 1' > /www/index.html

EXPOSE 8000

CMD ["/usr/bin/httpd", "-f", "-p", "8000", "-h", "/www"]