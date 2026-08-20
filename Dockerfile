FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

COPY app.py extract_roots.py match_buckets.py get_tooltip.py bucket_library.json ./
COPY templates/ templates/

ENV PORT=7860
ENV FLASK_DEBUG=0
EXPOSE 7860

CMD ["python", "app.py"]
