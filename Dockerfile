FROM busybox:musl

WORKDIR /www
RUN echo '{"status":"healthy"}' > /www/health && \
    echo 'CloudForge Application - Version 1' > /www/index.html

COPY . /www

EXPOSE 8000

CMD ["httpd", "-f", "-v", "-p", "8000", "-h", "/www"]