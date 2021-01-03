get_gcp_cluster:
	gcloud container clusters get-credentials stocker --zone europe-west2-b --project stocker-300519


build_push:
	docker build -t stocker -f Dockerfile .
	docker tag stocker:latest eu.gcr.io/stocker-300519/stocker:latest
	docker push eu.gcr.io/stocker-300519/stocker:latest

update_deployment: get_gcp_cluster
	kubectl apply -f deployment.yaml

deploy: get_gcp_cluster
	kubectl patch deployment stocker-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}"
