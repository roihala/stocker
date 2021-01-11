FROM python:3.8.3-slim-buster

COPY ./assets ./

RUN dpkg-deb -x google-chrome-stable_current_amd64.deb / && \
    apt-get install -f -y

COPY ./requirements.txt /code/requirements.txt
RUN pip3 install -r /code/requirements.txt

COPY ./ /code/
RUN chmod 755 /code/

ENV PYTHONPATH /code

CMD [ "python", "./code/stocker_alerts_bot.py" ]
