def get_ecs_cluster(client, tags: dict):
	paginator = client.get_paginator('list_clusters')

	for page in paginator.paginate():
		cluster_arns = page['clusterArns']

		clusters_info = client.describe_clusters(clusters=cluster_arns, include=['TAGS'])['clusters']
		for cluster in clusters_info:
			cluster_tags = {tag['key']: tag['value'] for tag in cluster.get('tags', [])}

			if all(tag in cluster_tags.items() for tag in tags.items()):
				return cluster['clusterArn']

	return None


def get_services_in_cluster(client, cluster_arn: str, search_word: str):
	services = client.list_services(cluster=cluster_arn)['serviceArns']
	filtered_services = [service for service in services if search_word in service]
	return filtered_services


def find_task_count_for_services(client, cluster_arn: str, list_of_services_arns: list):
	number_of_tasks = {}
	for service_arn in list_of_services_arns:
		service_info = client.describe_services(cluster=cluster_arn, services=[service_arn])['services'][0]
		task_count = service_info.get('runningCount')
		print(f"Current tasks for {service_arn} in running state: {task_count}")
		number_of_tasks[service_arn] = task_count
	return number_of_tasks


def update_service_task_count(client, cluster_arn: str, service_arn: str, desired_count: int, wait: bool = True,
                              force: bool = False):
	try:
		client.update_service(cluster=cluster_arn, service=service_arn, desiredCount=desired_count,
		                      forceNewDeployment=force)
		if wait:
			waiter = client.get_waiter('services_stable')
			waiter.wait(cluster=cluster_arn, services=[service_arn])
		return True
	except Exception as e:
		print(f"During scaling the service {service_arn} to {desired_count} an error occurred:")
		print(e)
		return False


def scale_up_ecs_tasks(client, tags: dict):
	cluster_arn = get_ecs_cluster(client=client, tags=tags)
	first_tag_key = [key for key in tags.values()][0]
	if cluster_arn:
		services_with_keyword = get_services_in_cluster(cluster_arn=cluster_arn, client=client,
		                                                search_word=first_tag_key)
		if services_with_keyword:
			task_count_per_service = find_task_count_for_services(client=client, cluster_arn=cluster_arn,
			                                                      list_of_services_arns=services_with_keyword)
			# Scale tasks
			for service_arn, task_count in task_count_per_service.items():
				print(f"Scaling {service_arn} to {task_count * 2}")
				update_service_task_count(client=client, cluster_arn=cluster_arn, service_arn=service_arn,
				                          desired_count=task_count * 2, wait=True)

		else:
			print(f"No services for the application {first_tag_key} was found.")


def scale_down_ecs_tasks(client, tags: dict):
	cluster_arn = get_ecs_cluster(client=client, tags=tags)
	first_tag_key = [key for key in tags.values()][0]
	if cluster_arn:
		services_with_keyword = get_services_in_cluster(cluster_arn=cluster_arn, client=client,
		                                                search_word=first_tag_key)
		if services_with_keyword:
			task_count_per_service = find_task_count_for_services(client=client, cluster_arn=cluster_arn,
			                                                      list_of_services_arns=services_with_keyword)
			# Scale tasks
			for service_arn, task_count in task_count_per_service.items():
				print(f"Current task number in service {service_arn}: {task_count}")
				print(f"Scaling {service_arn} to {int(task_count / 2)}")
				update_service_task_count(client=client, cluster_arn=cluster_arn, service_arn=service_arn,
				                          desired_count=int(task_count / 2), wait=False, force=True)

		else:
			print(f"No services for the application {first_tag_key} was found.")
