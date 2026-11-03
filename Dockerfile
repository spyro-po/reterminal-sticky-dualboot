FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

# A fixed Debian snapshot pins OS dependency resolution as well as the base image.
RUN rm -f /etc/apt/sources.list.d/debian.sources && \
    printf '%s\n' 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261102T000000Z bookworm main' > /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential cmake ninja-build xz-utils libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

ENV IDF54_PATH=/opt/esp/idf \
    IDF54_PYTHON=/opt/esp/idf-python/bin/python \
    IDF_PYTHON_ENV_PATH=/opt/esp/idf-python \
    IDF_TOOLS_PATH=/opt/esp/tools \
    IDF_PATH=/opt/esp/idf \
    PATH=/opt/sticky/python/bin:/usr/local/bin:/usr/bin:/bin \
    HOME=/tmp/sticky-home \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STICKY_CONTAINER=1 \
    UV_CONSTRAINT=/opt/sticky/locks/requirements-pio.lock \
    UV_BUILD_CONSTRAINT=/opt/sticky/locks/requirements-pio.lock \
    TZ=UTC

COPY docker/requirements-pio.lock docker/requirements-idf.lock docker/espidf.constraints.v5.4.txt /opt/sticky/locks/
RUN python -m venv /opt/sticky/python && \
    /opt/sticky/python/bin/python -m pip install --no-cache-dir pip==26.2.2 && \
    /opt/sticky/python/bin/python -m pip install --no-cache-dir -r /opt/sticky/locks/requirements-pio.lock && \
    python -m venv /opt/esp/idf-python && \
    /opt/esp/idf-python/bin/python -m pip install --no-cache-dir pip==26.2.2 && \
    /opt/esp/idf-python/bin/python -m pip install --no-cache-dir -r /opt/sticky/locks/requirements-idf.lock && \
    /opt/sticky/python/bin/python -m pip check && /opt/esp/idf-python/bin/python -m pip check

RUN git clone --branch v5.4 --depth 1 --recurse-submodules --shallow-submodules https://github.com/espressif/esp-idf.git /opt/esp/idf && \
    test "$(git -C /opt/esp/idf rev-parse HEAD)" = 67c1de1eebe095d554d281952fde63c16ee2dca0 && \
    git config --system --add safe.directory /opt/esp/idf && \
    git -C /opt/esp/idf submodule foreach --recursive 'git config --system --add safe.directory "$PWD"' && \
    python /opt/esp/idf/tools/idf_tools.py install xtensa-esp-elf@esp-14.2.0_20241119 && \
    cp /opt/sticky/locks/espidf.constraints.v5.4.txt /opt/esp/tools/ && \
    /opt/esp/idf-python/bin/python /opt/esp/idf/tools/idf_tools.py check-python-dependencies

# No CrossPoint compile, vendor download, Flash image or host cache is in a layer.
COPY VERSION README.md LICENSE NOTICE SOURCE_FILES.sha256 requirements-build.txt /opt/sticky/source/
COPY firmware /opt/sticky/source/firmware/
COPY crosspoint /opt/sticky/source/crosspoint/
COPY partitions /opt/sticky/source/partitions/
COPY patches /opt/sticky/source/patches/
COPY scripts /opt/sticky/source/scripts/
COPY tests /opt/sticky/source/tests/
COPY manifests /opt/sticky/source/manifests/
COPY licenses /opt/sticky/source/licenses/
COPY docker /opt/sticky/source/docker/
RUN python /opt/sticky/source/scripts/audit_builder.py --source /opt/sticky/source && \
    chmod 755 /opt/sticky/source/docker/entrypoint.sh && \
    rm -rf /tmp/sticky-home /tmp/sticky-project

USER 1000:1000
WORKDIR /tmp
VOLUME ["/output"]
ENTRYPOINT ["/opt/sticky/source/docker/entrypoint.sh"]
CMD ["list"]
