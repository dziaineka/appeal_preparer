FROM python:3.8-buster

RUN apt-get update && apt-get install -y chromium
RUN apt-get install -y chromium-driver

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./main.py" ]