FROM python:3.8.3-slim-buster

COPY ./requirements.txt /code/requirements.txt
RUN pip3 install -r /code/requirements.txt

COPY ./ /code/
RUN chmod 755 /code/

ENV PYTHONPATH /code
ENV GOOGLE_APPLICATION_CREDENTIALS /code/credentials/stocker.json

EXPOSE 8000
ENTRYPOINT ["streamlit", "run"]
CMD ["/code/toolkit.py"]
