FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxrender1 libxext6 libsm6 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -u 10001 -s /usr/sbin/nologin runner \
 && pip install --no-cache-dir build123d==0.12.0
WORKDIR /app
COPY runner.py server.py /app/
USER 10001
ENV PORT=8080 HOST=0.0.0.0 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
CMD ["python", "/app/server.py"]
# Run with (hardening):
#   docker run --read-only --tmpfs /tmp:size=256m --cap-drop ALL --security-opt no-new-privileges \
#     --pids-limit 128 --memory 3g --cpus 1 -e EXEC_SECRET=... -p 8080:8080 img
# Network: block OUTBOUND traffic at the platform level (Cloud Run: VPC egress deny; Fly: no easy
# egress block, so rely on AST allowlist + no secrets in the container beyond EXEC_SECRET).
