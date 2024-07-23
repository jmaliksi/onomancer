FROM python:3.11-slim
EXPOSE 5001

WORKDIR /app
RUN mkdir /app/data
VOLUME /app/data

COPY . ./
RUN pip install -r requirements.txt
RUN pip install gunicorn

RUN python -m onomancer.database bootstrap load
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "onomancer.app:app"]
