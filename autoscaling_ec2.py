def get_asg_by_tg(tags: dict, client) -> list:
	asg_names = []
	paginator = client.get_paginator('describe_auto_scaling_groups')
	page_iterator = paginator.paginate(
		PaginationConfig={'PageSize': 100}
	)
	filter_name = 'AutoScalingGroups[]'
	for tag in tags:
		filter_name = ('{} | [?contains(Tags[?Key==`{}`].Value, `{}`)]'.format(filter_name, tag, tags[tag]))
	filtered_asgs = page_iterator.search(filter_name)
	for key_data in filtered_asgs:
		asg_names.append(key_data["AutoScalingGroupName"])

	return asg_names


def get_asg_capacity(asg_name: str, client):
	description = client.describe_auto_scaling_groups(
		AutoScalingGroupNames=[asg_name])
	return description["AutoScalingGroups"][0]["DesiredCapacity"]


def scale_asg(asg_name: str, client, capacity: int, scale_in_protection_enabled: bool = True) -> any:
	capacity = int(capacity)
	print(f"Starting scaling for {asg_name} to desired capacity = {capacity}")
	scaling = client.update_auto_scaling_group(
		AutoScalingGroupName=asg_name,
		MaxSize=capacity,
		DesiredCapacity=capacity,
		NewInstancesProtectedFromScaleIn=scale_in_protection_enabled
	)

	return scaling


def get_old_ec2_ids(asg_name: str, asg_client) -> list:
	asg_description = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
	instance_ids = []
	for i in asg_description['AutoScalingGroups']:
		for k in i['Instances']:
			instance_ids.append(k['InstanceId'])

	return instance_ids


def terminate_old_ec2(ec2_ids_to_terminate: list, client):
	client.terminate_instances(InstanceIds=ec2_ids_to_terminate)


def disable_scale_in_protection(client, asg_name: str):
	print("Disabling scale in protection from new instances.")
	asg_description = client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
	instance_ids = []
	for i in asg_description['AutoScalingGroups']:
		for k in i['Instances']:
			instance_ids.append(k['InstanceId'])
	client.set_instance_protection(
		InstanceIds=instance_ids,
		AutoScalingGroupName=asg_name,
		ProtectedFromScaleIn=False
	)
