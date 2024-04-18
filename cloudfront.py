import datetime
import json


def get_cloudfront_distribution(client, tags) -> list:
	paginator = client.get_paginator('list_distributions')
	if type(tags) is "str":
		tags = json.loads(tags)
	print(type(tags))
	new_cf_tag_dict = {}
	distribution_data = []
	print("Getting cloudfront ID to ivalidate")
	for page in paginator.paginate():
		# Get list of CloudFront distributions from current page
		distributions = page['DistributionList'].get('Items', [])

		# Iterate over distributions to find the one with matching tags
		for distribution in distributions:
			# Get distribution tags
			distribution_tags = client.list_tags_for_resource(Resource=distribution['ARN'])['Tags'].get('Items', [])
			if distribution_tags == []:
				pass
			else:
				for kv_pair in distribution_tags:
					new_cf_tag_dict[kv_pair["Key"]] = kv_pair["Value"]
				if all(tag in new_cf_tag_dict.items() for tag in tags.items()):
					distribution_data.append(distribution['Id'])
					print(f"Distribution ID to invalidate is {distribution['Id']}")
	return distribution_data


def invalidate_cloudfront(client, id_list: list):
	dt = datetime.datetime.utcnow()
	for id in id_list:
		print(f"Invalidating cloudfront ID: {id}")
		response = client.create_invalidation(
			DistributionId=id,
			InvalidationBatch={
				'Paths': {
					'Quantity': 1,
					'Items': [
						'/',
					]
				},
				'CallerReference': str(int(datetime.datetime.timestamp(dt)))
			}
		)
		print(response)
