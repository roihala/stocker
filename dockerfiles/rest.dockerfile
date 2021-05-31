FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

COPY ./requirements.txt /code/requirements.txt
RUN pip3 install -r /code/requirements.txt

COPY ./ /code/
RUN chmod 755 /code/

ENV PYTHONPATH /code
ENV GOOGLE_APPLICATION_CREDENTIALS /code/credentials/stocker.json
ENV PYTHONUNBUFFERED=1
ENV WORKERS_PER_CORE=4
ENV PORT=8000
ENV MODULE_NAME="rest"

EXPOSE 8000
