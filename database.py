import time


def get_rds_information(client, tags: dict):
	paginator = client.get_paginator('describe_db_instances')
	page_iterator = paginator.paginate()
	filter_name = 'DBInstances[]'
	db_information = {}
	for tag in tags:
		filter_name = ('{} | [?contains(TagList[?Key==`{}`].Value, `{}`)]'.format(filter_name, tag, tags[tag]))
	filtered_iterator = page_iterator.search(filter_name)
	for key_data in filtered_iterator:
		db_information["arn"] = key_data["DBInstanceArn"]
		db_information["name"] = key_data["DBInstanceIdentifier"]
	return db_information


def get_bg_status(client, deployment_id: str, sleep_timer: int = 90):
	statuses = {}
	description = client.describe_blue_green_deployments(BlueGreenDeploymentIdentifier=deployment_id)
	status = description["BlueGreenDeployments"][0]["Status"]
	# need fix, to check weather TargetMember is in parameters or not to not waste 90 sec each time
	time.sleep(sleep_timer)
	while True:
		try:
			target_state = client.describe_db_instances(
				DBInstanceIdentifier=description["BlueGreenDeployments"][0]["SwitchoverDetails"][0]["TargetMember"])
		except Exception:
			description = client.describe_blue_green_deployments(BlueGreenDeploymentIdentifier=deployment_id)
			target_state = client.describe_db_instances(
				DBInstanceIdentifier=description["BlueGreenDeployments"][0]["SwitchoverDetails"][0]["TargetMember"])
		target_status = target_state["DBInstances"][0]["DBInstanceStatus"]
		break
	statuses["deployment_status"] = status
	statuses["replica_status"] = target_status
	statuses["target_arn"] = description["BlueGreenDeployments"][0]["Target"]
	statuses["source_arn"] = description["BlueGreenDeployments"][0]["Source"]
	return statuses


def rds_bg(client, rds_arn: str, rds_name: str):
	print("Creating blue/green deployment.")
	bg = client.create_blue_green_deployment(BlueGreenDeploymentName=f"{rds_name}-deployment", Source=rds_arn)
	deployment_id = bg["BlueGreenDeployment"]["BlueGreenDeploymentIdentifier"]
	status = get_bg_status(client=client, deployment_id=deployment_id)
	while status["deployment_status"] != "AVAILABLE" and status["replica_status"] != "available":
		print("Still creating blue/green deployment.")
		status = get_bg_status(client=client, deployment_id=deployment_id)
	print("Blue/green deployment is created.")
	return deployment_id


def rds_switchover(client, deployment_id: str):
	print("Check target instance is available")
	status = get_bg_status(client=client, deployment_id=deployment_id)
	target_status = client.describe_db_instances(DBInstanceIdentifier=status["target_arn"])["DBInstances"][0][
		"DBInstanceStatus"]
	while target_status != "available":
		print(f"Target instance is still in {target_status} status")
		status = get_bg_status(client=client, deployment_id=deployment_id)
		target_status = client.describe_db_instances(DBInstanceIdentifier=status["target_arn"])["DBInstances"][0][
			"DBInstanceStatus"]
		time.sleep(30)

	print("Starting blue/green deployment switchover.")
	client.switchover_blue_green_deployment(
		BlueGreenDeploymentIdentifier=deployment_id,
		SwitchoverTimeout=900
	)
	while status["deployment_status"] != "SWITCHOVER_COMPLETED" and status["replica_status"] != "available":
		time.sleep(30)
		print("Status:", status)
		print("Switchover is still in progress.")
		status = get_bg_status(client=client, deployment_id=deployment_id)
	print("Switchover is finished.")
	return True


def create_rds_snapshot(client, rds_arn: str) -> bool:
	import datetime
	snapshot_name = rds_arn.split(":")[-1] + "-snapshot-" + str(datetime.datetime.now().strftime("%m-%d-%Y"))

	response = client.describe_db_instances(DBInstanceIdentifier=rds_arn.split(":")[-1])
	status = response['DBInstances'][0]['DBInstanceStatus']
	while status != "Available":
		time.sleep(30)
		print(f"RDS is not in Available status yet. Status is: {status}")
		response = client.describe_db_instances(DBInstanceIdentifier=rds_arn.split(":")[-1])
		status = response['DBInstances'][0]['DBInstanceStatus']
	try:
		print("Creating manual snapshot of RDS.")
		client.create_db_snapshot(DBSnapshotIdentifier=snapshot_name, DBInstanceIdentifier=rds_arn.split(":")[-1])
		waiter = client.get_waiter('db_snapshot_available')
		while waiter.wait(DBInstanceIdentifier=rds_arn.split(":")[-1], DBSnapshotIdentifier=snapshot_name):
			print("Still creating snapshot.")
			time.sleep(30)
		return True
	except Exception as e:
		print("During rds snapshot process an exception occurred.", e)
		return False


def delete_rds_and_deployment(client, deployment_id: str, rds_arn: str):
	try:
		description = client.describe_blue_green_deployments(BlueGreenDeploymentIdentifier=deployment_id)
		status = description["BlueGreenDeployments"][0]["Status"]
		while status != "SWITCHOVER_COMPLETED":
			print(f"Checking for switchover is finished. Status: {status}")
			time.sleep(10)
			status = description["BlueGreenDeployments"][0]["Status"]
		print(f"Deleting deployment {deployment_id}")
		client.delete_blue_green_deployment(BlueGreenDeploymentIdentifier=deployment_id, DeleteTarget=False)
		print(f"Deleting rds {rds_arn}")
		client.delete_db_instance(DBInstanceIdentifier=rds_arn.split(":")[-1], SkipFinalSnapshot=True)
		return True
	except Exception as e:
		print("During rds snapshot process an exception occurred.", e)
		return False
