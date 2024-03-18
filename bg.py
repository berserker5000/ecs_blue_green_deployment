import os
import json
import boto3

import autoscaling_ec2
import database
import ecs

access_key_id = os.getenv("INPUT_ACCESS_KEY_ID") or None
secret_access_key = os.getenv("INPUT_SECRET_ACCESS_KEY") or None
region_name = os.getenv("INPUT_REGION_NAME") or "us-east-1"
profile_name = os.getenv("INPUT_PROFILE_NAME") or None
tags = os.getenv("INPUT_APPLICATION_TAGS") or None

if tags is None:
	print("You haven't specify any tags of your application to operate on. Buy.")
	exit(1)
else:
	tags = json.loads(tags)

if access_key_id is not None and secret_access_key is not None:
	session = boto3.Session(aws_access_key_id=access_key_id, region_name=region_name,
	                        aws_secret_access_key=secret_access_key)
elif profile_name is not None:
	session = boto3.Session(profile_name=profile_name, region_name=region_name)
else:
	print("You haven't specify nor AK/SK nor profile to be used. Buy.")
	exit(1)

ec2_client = session.client("ec2")
rds_client = session.client("rds")
asg_client = session.client("autoscaling")
ecs_client = session.client("ecs")


def main():
	rds_data = database.get_rds_information(client=rds_client, tags=tags)
	autoscaling_groups = autoscaling_ec2.get_asg_by_tg(tags=tags, client=asg_client)

	# --- SCALE UP ---
	print("Scaling service UP.")
	for asg in autoscaling_groups:
		# getting number of EC2 in ASG
		capacity = autoscaling_ec2.get_asg_capacity(asg_name=asg, client=asg_client)
		# scaling x2 for ec2 instance
		autoscaling_ec2.scale_asg(asg_name=asg, capacity=capacity * 2, client=asg_client,
		                          scale_in_protection_enabled=True)

	# Scale in
	print("Scaling ECS tasks x2.")
	ecs.scale_ecs_tasks(client=ecs_client, tags=tags, multiplier=2)

	# bg deployment for RDS
	print("Creating Blue/Green deployment for RDS.")
	deployment_id = database.rds_bg(client=rds_client, rds_arn=rds_data["arn"], rds_name=rds_data["name"])
	# switch RDS
	print("Switching over RDS in the deployment.")
	switchover_is_done = database.rds_switchover(client=rds_client, deployment_id=deployment_id)

	# --- SCALE DOWN ---
	print("Scaling down the application.")
	for asg in autoscaling_groups:
		# Getting EC2 ids for old instances
		old_ids = autoscaling_ec2.get_old_ec2_ids(asg_name=asg, asg_client=asg_client)
		# getting number of EC2 in ASG
		capacity = autoscaling_ec2.get_asg_capacity(asg_name=asg, client=asg_client)
		# scaling x1 for ec2 instance
		print("Scaling down Autoscaling group.")
		autoscaling_ec2.scale_asg(asg_name=asg, capacity=capacity / 2, client=asg_client)
		# terminate old EC2
		print("Terminating old EC2 instances.")
		autoscaling_ec2.terminate_old_ec2(client=ec2_client, ec2_ids_to_terminate=old_ids)
		print("Disabling scale-in protection.")
		autoscaling_ec2.disable_scale_in_protection(client=asg_client, asg_name=asg)

	# Scale down
	print("Scaling down ECS tasks.")
	ecs.scale_ecs_tasks(client=ecs_client, tags=tags, multiplier=0.5, wait=False)

	if switchover_is_done:
		deployment_data = database.get_bg_status(client=rds_client, deployment_id=deployment_id, sleep_timer=0)
		# snapshot old rds
		print("Making a snapshot for old RDS.")
		is_snapshot_done = database.create_rds_snapshot(client=rds_client, rds_arn=deployment_data["source_arn"])
		if is_snapshot_done:
			print("Snapshot is created, now you can delete an old RDS and deployment.")
			database.delete_rds_and_deployment(client=rds_client, rds_arn=deployment_data["source_arn"],
			                                   deployment_id=deployment_id)


main()
