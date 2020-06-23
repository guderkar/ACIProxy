FROM python:3.7.7-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
COPY script.py ./

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "./script.py" ]