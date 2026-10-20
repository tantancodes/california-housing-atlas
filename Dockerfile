FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock pyproject.toml ./
COPY atlas ./atlas
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
COPY app.py ./
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY data/public ./data/public
COPY sql ./sql
RUN useradd --create-home atlas
USER atlas
ENV ATLAS_ENABLE_PRIVATE=0
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
