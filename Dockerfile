FROM alpine:3.23

RUN mkdir -p /www && \
    echo '{"status":"healthy"}' > /www/health && \
    echo 'CloudForge Application - Version 1' > /www/index.html

EXPOSE 8000

CMD ["busybox", "httpd", "-f", "-p", "8000", "-h", "/www"]