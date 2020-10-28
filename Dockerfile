FROM python:3.8
EXPOSE 5001

WORKDIR /app

COPY . ./
RUN pip install -r requirements.txt

CMD ["python", "-m", "onomancer.database", "clear", "bootstrap", "load"]
