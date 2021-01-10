get_gcp_cluster:
	gcloud container clusters get-credentials stocker --zone europe-west2-b --project stocker-300519


collector_build_push:
	docker build -t stocker -f collector.dockerfile .
	docker tag stocker:latest eu.gcr.io/stocker-300519/stocker:latest
	docker push eu.gcr.io/stocker-300519/stocker:latest

collector_update_deployment: get_gcp_cluster
	kubectl apply -f deployment.yaml

collector_deploy: get_gcp_cluster
	kubectl patch deployment stocker-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}"

collector_delete_pod:
	kubectl delete pods -l run=stocker-app || true

telegram_build_push:
	docker build -t telegram-bot -f telegram_bot.dockerfile .
	docker tag telegram-bot:latest eu.gcr.io/stocker-300519/telegram-bot:latest
	docker push eu.gcr.io/stocker-300519/telegram-bot:latest

telegram_update_deployment: get_gcp_cluster
		kubectl apply -f telegram_bot_deployment.yaml

telegram_deploy: get_gcp_cluster
	kubectl patch deployment telegram-bot-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}"

telegram_delete_pod:
	kubectl delete pods -l run=telegram-bot-app || true


