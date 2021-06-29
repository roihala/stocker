FROM google/cloud-sdk:alpine
RUN gcloud components install kubectl
WORKDIR /app
COPY . .
ENTRYPOINT ["./execute.sh"]