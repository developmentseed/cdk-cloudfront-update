import json
import boto3
import cfnresponse
import logging

logger = logging.getLogger(__name__)

client = boto3.client("cloudfront")


def lambda_handler(event, context):
    if event["RequestType"] not in ["Create", "Update"]:
        return cfnresponse.send(
            event, context, cfnresponse.SUCCESS, {"msg": "No action to be taken"}
        )

    try:
        config_res = client.get_distribution_config(
            Id=event["ResourceProperties"]["Id"]
        )
        config_req = dict(config_res["DistributionConfig"])
        ETag = config_res["ETag"]
        origin_config = json.loads(event["ResourceProperties"]["OriginConfig"])
        behavior_config = json.loads(event["ResourceProperties"]["BehaviorConfig"])

        origins_by_id = {
            origin["Id"]: origin for origin in config_req["Origins"].get("Items", [])
        }

        origins_by_id[origin_config["Id"]] = origin_config

        origins = {
            "Items": list(origins_by_id.values()),
            "Quantity": len(origins_by_id),
        }

        config_req["Origins"] = origins

        # avoid adding duplicate path patterns
        behaviors_by_path = {
            behavior["PathPattern"]: behavior
            for behavior in config_req["CacheBehaviors"].get("Items", [])
        }

        behaviors_by_path[behavior_config["PathPattern"]] = behavior_config

        cache_behaviors = {
            "Items": list(behaviors_by_path.values()),
            "Quantity": len(behaviors_by_path),
        }

        config_req["CacheBehaviors"] = cache_behaviors

        # print(json.dumps(config_req, indent=2))

        response = client.update_distribution(
            Id=event["ResourceProperties"]["Id"],
            IfMatch=ETag,
            DistributionConfig=config_req,
        )

        print("Response", response)
        print("SUCCESS")
        return cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        logger.exception(str(e))
        return cfnresponse.send(event, context, cfnresponse.FAILED, {"message": str(e)})
