# Built from nothing, so the build pulls no image and reaches no network: the build
# script brings the machine's static busybox into the build context as rootfs/ (see
# the recipe beside this source tree).
FROM scratch
COPY rootfs/ /
# A real RUN step, executed by the bench's own daemon, with nothing to download.
RUN ["/bin/busybox", "--install", "-s", "/bin"]
COPY main.sh /app/main.sh
ENTRYPOINT ["/bin/sh", "/app/main.sh"]
