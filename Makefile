get_gcp_cluster:
	gcloud container clusters get-credentials stocker --zone europe-west2-a --project stocker-300519


all: collector alerter telegram records rest scheduler

collector: collector_build_push collector_delete_pod

collector_build_push:
	docker build -t collector -f dockerfiles/collector.dockerfile .
	docker tag collector:latest eu.gcr.io/stocker-300519/collector:latest
	docker push eu.gcr.io/stocker-300519/collector:latest

collector_update_deployment: get_gcp_cluster
	kubectl apply -f kubefiles/collector_deployment.yaml

collector_deploy: get_gcp_cluster
	kubectl patch deployment collector-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}""

collector_delete_pod:
	kubectl delete pods -l run=collector-app || true


telegram: telegram_build_push telegram_delete_pod

telegram_build_push:
	docker build -t telegram-bot -f dockerfiles/telegram_bot.dockerfile .
	docker tag telegram-bot:latest eu.gcr.io/stocker-300519/telegram-bot:latest
	docker push eu.gcr.io/stocker-300519/telegram-bot:latest

telegram_update_deployment: get_gcp_cluster
		kubectl apply -f kubefiles/telegram_bot_deployment.yaml

telegram_deploy: get_gcp_cluster
	kubectl patch deployment telegram-bot-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}"""

telegram_delete_pod:
	kubectl delete pods -l run=telegram-bot-app || true

telegram_run_local:
	docker run -it --rm -e ENV=production -e MONGO_URI="mongodb+srv://stocker:halamish123@cluster2.3nsz4.mongodb.net/stocker" -e TELEGRAM_TOKEN="1177225094:AAGtBg9BzIJVVXHelSSYnaQB6HBhyG1obiQ" telegram-bot


alerter: alerter_build_push alerter_delete_pod

alerter_build_push:
	docker build -t alerter -f dockerfiles/alerter.dockerfile .
	docker tag alerter:latest eu.gcr.io/stocker-300519/alerter:latest
	docker push eu.gcr.io/stocker-300519/alerter:latest

alerter_update_deployment: get_gcp_cluster
		kubectl apply -f kubefiles/alerter_deployment.yaml

alerter_deploy: get_gcp_cluster
	kubectl patch deployment alerter-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}"""

alerter_delete_pod:
	kubectl delete pods -l run=alerter-app || true

alerter_run_local:
	docker run -it --rm -e ENV=production -e MONGO_URI="mongodb+srv://stocker:halamish123@cluster2.3nsz4.mongodb.net/stocker" -e TELEGRAM_TOKEN="1177225094:AAGtBg9BzIJVVXHelSSYnaQB6HBhyG1obiQ" -e REDIS_IP="10.80.176.3" alerter


records: records_build_push records_delete_pod
records_build_push:
	docker build -t records -f dockerfiles/records.dockerfile .
	docker tag records:latest eu.gcr.io/stocker-300519/records:latest
	docker push eu.gcr.io/stocker-300519/records:latest

records_update_deployment: get_gcp_cluster
	kubectl apply -f kubefiles/records_deployment.yaml

records_deploy: get_gcp_cluster
	kubectl patch deployment records-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}""

records_delete_pod:
	kubectl delete pods -l run=records-app || true


records_guesser: records_guesser_build records_guesser_delete_pod

records_guesser_build:
	docker build -t records-guesser -f dockerfiles/records.dockerfile .
	docker tag records-guesser:latest eu.gcr.io/stocker-300519/records-guesser:latest
	docker push eu.gcr.io/stocker-300519/records-guesser:latest

records_guesser_update_deployment: get_gcp_cluster
	kubectl apply -f kubefiles/records_guesser_deployment.yaml

records_guesser_deploy: get_gcp_cluster
	kubectl patch deployment records-guesser-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}""

records_guesser_delete_pod:
	kubectl delete pods -l run=records-guesser-app || true


rest: rest_build_push rest_delete_pod

rest_build_push:
	docker build -t stocker -f dockerfiles/rest.dockerfile .
	docker tag stocker:latest eu.gcr.io/stocker-300519/rest:latest
	docker push eu.gcr.io/stocker-300519/rest:latest

rest_update_deployment: get_gcp_cluster
	kubectl apply -f kubefiles\rest

rest_deploy: get_gcp_cluster
	kubectl patch deployment rest-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}""

rest_delete_pod:
	kubectl delete pods -l run=rest-app || true


scheduler: scheduler_build scheduler_delete_pod

scheduler_build:
	docker build -t collector-scheduler -f dockerfiles/scheduler.dockerfile .
	docker tag collector-scheduler:latest eu.gcr.io/stocker-300519/collector-scheduler:latest
	docker push eu.gcr.io/stocker-300519/collector-scheduler:latest

scheduler_update_deployment: get_gcp_cluster
	kubectl apply -f kubefiles\collector_scheduler.yaml

scheduler_deploy: get_gcp_cluster
	kubectl patch deployment collector-scheduler-app -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"date\":\"`date +'%s'`\"}}}}}""

scheduler_delete_pod:
	kubectl delete pods -l run=collector-scheduler-app || true

priority_build:
	docker build -t priority-scheduler -f dockerfiles/priority.dockerfile .
	docker tag collector-scheduler:latest eu.gcr.io/stocker-300519/priority-scheduler:latest
	docker push eu.gcr.io/stocker-300519/priority-scheduler:latest

priority_update_deployment: get_gcp_cluster
	kubectl apply -f kubefiles\priority_scheduler.yaml

stop_cron_jobs: get_gcp_cluster
	kubectl patch cronjobs scale-down-job -p "{\"spec\" : {\"suspend\" : true }}"
	kubectl patch cronjobs scale-up-job -p "{\"spec\" : {\"suspend\" : true }}"
	kubectl patch cronjobs scale-up-job-once-an-hour -p "{\"spec\" : {\"suspend\" : true }}"
	kubectl patch cronjobs scale-down-job-once-an-hour -p "{\"spec\" : {\"suspend\" : true }}"
	kubectl patch cronjobs scale-up-job-once-an-hour-non-working-day -p "{\"spec\" : {\"suspend\" : true }}"
	kubectl patch cronjobs scale-down-job-once-an-hour-non-working-day -p "{\"spec\" : {\"suspend\" : true }}"

resume_cron_jobs: get_gcp_cluster
	kubectl patch cronjobs scale-down-job -p "{\"spec\" : {\"suspend\" : false }}"
	kubectl patch cronjobs scale-up-job -p "{\"spec\" : {\"suspend\" : false }}"
	kubectl patch cronjobs scale-up-job-once-an-hour -p "{\"spec\" : {\"suspend\" : false }}"
	kubectl patch cronjobs scale-down-job-once-an-hour -p "{\"spec\" : {\"suspend\" : false }}"
	kubectl patch cronjobs scale-up-job-once-an-hour-non-working-day -p "{\"spec\" : {\"suspend\" : false }}"
	kubectl patch cronjobs scale-down-job-once-an-hour-non-working-day -p "{\"spec\" : {\"suspend\" : false }}"