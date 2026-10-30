# Built from nothing, so the build pulls no image and reaches no network: the build
# script brings the bench's own busybox and the musl loader it links against into the
# build context as rootfs/ (see examples/recipes/instant_docker_hello_world).
FROM scratch
COPY rootfs/ /
# A real RUN step, executed by the bench's own daemon, with nothing to download.
RUN ["/bin/busybox", "--install", "-s", "/bin"]
COPY main.sh /app/main.sh
ENTRYPOINT ["/bin/sh", "/app/main.sh"]
