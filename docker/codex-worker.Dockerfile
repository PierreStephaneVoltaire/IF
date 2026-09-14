FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates nodejs npm tini && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/if
RUN pip install --no-cache-dir openai-codex==0.154.0 httpx pydantic PyYAML Jinja2 fastapi uvicorn
COPY app/src/execution /opt/if/app/src/execution
COPY app/src/flow/codex_llm.py /opt/if/app/src/flow/codex_llm.py
COPY app/src/agent/codex_specialists.py /opt/if/app/src/agent/codex_specialists.py
COPY specialists /opt/if/specialists
COPY skills /opt/if/skills
COPY app/main_system_prompt.txt /opt/if/app/main_system_prompt.txt
ENV PYTHONPATH=/opt/if/app/src PYTHONUNBUFFERED=1 CODEX_HOME=/var/lib/codex IF_WORKER_ROOT=/work TMPDIR=/work
RUN useradd -m -u 10001 worker && mkdir -p /var/lib/codex /work && chown -R worker:worker /var/lib/codex /work
USER worker
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "execution.worker"]
