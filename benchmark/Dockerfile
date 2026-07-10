FROM myna-messenger:local

USER root
WORKDIR /app

COPY benchmark/requirements.txt /tmp/myna-benchmark-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/myna-benchmark-requirements.txt

COPY --chown=appuser:appuser benchmark /benchmark

USER appuser
WORKDIR /app
ENTRYPOINT ["python"]
CMD ["/benchmark/runner/myna_distributed_pairs_latency_benchmark_test.py"]
