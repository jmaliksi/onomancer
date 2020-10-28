FROM python:3.8
EXPOSE 5001

WORKDIR /app
RUN mkdir /app/data
VOLUME /app/data

COPY . ./
RUN pip install -r requirements.txt

RUN python -m onomancer.database bootstrap load
CMD ["python", "-m", "onomancer"]
