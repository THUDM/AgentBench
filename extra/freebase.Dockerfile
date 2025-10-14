FROM python:3-slim

ENV PYTHONUNBUFFERED=1

ADD https://github.com/openlink/virtuoso-opensource/releases/download/v7.2.5/virtuoso-opensource.x86_64-generic_glibc25-linux-gnu.tar.gz /tmp/virtuoso.tar.gz
RUN tar -xzf /tmp/virtuoso.tar.gz -C /opt && \
    rm /tmp/virtuoso.tar.gz

ENV VIRTUOSO_HOME=/opt/virtuoso-opensource
ENV PATH="${VIRTUOSO_HOME}/bin:${PATH}"

ADD https://github.com/dki-lab/Freebase-Setup/raw/refs/heads/master/virtuoso.py /virtuoso.py
RUN sed -i 's|/home/dki_lab/tools/virtuoso/virtuoso-opensource|/opt/virtuoso-opensource|g' /virtuoso.py && \
    chmod +x /virtuoso.py

EXPOSE 3001/tcp
EXPOSE 13001/tcp

STOPSIGNAL SIGTERM

COPY --chmod=0755 extra/freebase-entrypoint.sh /entrypoint.sh

CMD ["/entrypoint.sh"]
