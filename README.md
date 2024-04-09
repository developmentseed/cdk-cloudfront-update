# CDK Cloudfront Update Construct

This CDK Construct allows users to add and update origins and behaviors on an existing Cloudfront Distribution.
This is specifically useful if you manage a Distribution through a separate CDK Stack and must import it into the Stack for one of your applications.

## Warnings

This Construct works by calling the Cloudfront API through a CustomResource and **makes no attempt to avoid destructive updates**. It reads the existing Cloudfront Distribution config and updates it with the provided origin and behavior. If the origin or behavior are already present on the Distribution, **it will overwrite them**. Origins are identified by their `Id` property and Behaviors are identified by their `PathPattern` property. If you provide an Origin with an `Id` that already exists on the Distribution, the **existing Origin with that `Id` will be overwritten**. If you provide a Behavior with a `PathPattern` that already exists on the Distribution, the **existing Behavior with that `PathPattern` will be overwritten**.

The flipside of this is the Construct does not touch any configuration in the Distribution that does not collide with the provided Origin or Behavior (on the assumption that you may be adding additional Origins and Behaviors in other Stacks). A side effect of this is if you run this Construct with a specific Origin `Id` and later change the `Id`, a new Origin will be created, but the previous Origin **will not be deleted**. You will need to manually delete the old Origin.

## Usage

```python
from constructs import Construct
from cdk_cloudfront_update.constructs import CloudfrontUpdate


class MyApi(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        distribution_arn: str,
        service_path_pattern: str,
        load_balancer_dns_name: str,
        **kwargs,
    ):
        """
        Add MyAPI service to the Cloudfront Distribution at the
        specified path.
        """
        super().__init__(scope, id, **kwargs)

        origin_id = "ApiLoadBalancer"

        CloudfrontUpdate(
            self,
            "my-api-cf-update",
            distribution_arn=distribution_arn,
            behavior_config={
                "PathPattern": service_path_pattern,
                "TargetOriginId": origin_id,
                "TrustedSigners": {"Enabled": False, "Quantity": 0},
                "TrustedKeyGroups": {"Enabled": False, "Quantity": 0},
                "ViewerProtocolPolicy": "redirect-to-https",
                "AllowedMethods": {
                    "Quantity": 7,
                    "Items": [
                        "HEAD",
                        "DELETE",
                        "POST",
                        "GET",
                        "OPTIONS",
                        "PUT",
                        "PATCH",
                    ],
                    "CachedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]},
                },
                "SmoothStreaming": False,
                "Compress": True,
                "LambdaFunctionAssociations": {"Quantity": 0},
                "FunctionAssociations": {"Quantity": 0},
                "FieldLevelEncryptionId": "",
                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",  # Managed CachingDisabled Policy
                "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",  # Managed AllViewer Origin Request Policy
            },
            origin_config={
                "Id": origin_id,
                "DomainName": load_balancer_dns_name,
                "OriginPath": "",
                "CustomHeaders": {"Quantity": 0},
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only",
                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                    "OriginReadTimeout": 60,
                    "OriginKeepaliveTimeout": 5,
                },
                "ConnectionAttempts": 3,
                "ConnectionTimeout": 10,
                "OriginShield": {"Enabled": False},
            },
        )
```

This Construct makes use of the Cloudfront API's `update-distribution`, so values for `behavior_config` and `origin_config` can be derived from the API docs for [CacheBehavior](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CacheBehavior.html) and [Origin](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_Origin.html).

## Permissions

By default, the Construct will create a Lambda function with permission to Get and Update the specified Distribution. In some cases, you may need to grant it additional permissions. For example, if you want to add a Lambda@Edge function to the CacheBehavior, you will need to grant additional Lambda permissions in order for the API call to succeed. For example:

```python
from aws_cdk import aws_lambda
from constructs import Construct
from cdk_cloudfront_update.constructs import CloudfrontUpdate


class MyApi(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        distribution_arn: str,
        service_path_pattern: str,
        load_balancer_dns_name: str,
        **kwargs,
    ):
        """
        Add MyAPI service to the Cloudfront Distribution at the
        specified path.
        """
        super().__init__(scope, id, **kwargs)

        # Create a Lambda Function for use with Lambda@Edge
        edge_fn_role = iam.Role(
            self,
            "EdgeFnRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("edgelambda.amazonaws.com"),
                iam.ServicePrincipal("lambda.amazonaws.com"),
            ),
        )
        edge_fn = aws_lambda.Function(
            self,
            "EdgeFn",
            handler="main.handler",
            role=thumbnail_role,
            code=aws_lambda.Code.from_asset(
                os.path.join(
                    os.path.dirname(__file__),
                    "edge_lambda_src",
                )
            ),
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            timeout=Duration.seconds(5),
        )

        cf_update_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "lambda:GetFunction",
                "lambda:EnableReplication*",
            ],
            resources=[edge_fn.current_version.function_arn],
        )

        origin_id = "ApiLoadBalancer"

        CloudfrontUpdate(
            self,
            "my-api-cf-update",
            distribution_arn=distribution_arn,
            lambda_execution_policy_statements=[associate_policy],
            behavior_config={
                ...
                "LambdaFunctionAssociations": {
                    "Quantity": 1,
                    "Items": [
                        {
                            "LambdaFunctionARN": edge_fn.current_version.function_arn,
                            "EventType": "viewer-request",
                            "IncludeBody": False,
                        },
                    ],
                },
            },
            origin_config={
                ...
            },
        )
```

## Creating Multiple Origins/Behaviors

You may need multiple instances of this Construct within the same Stack. If so, you will need to define a dependency between the CustomResource for each instance, such that they trigger sequentially and avoid collisions when calling the API. For example:

```python
api_cf = CloudfrontUpdate(
    self,
    "my-api-cf-update",
    ...
)

static_site_cf = CloudfrontUpdate(
    self,
    "my-static-site-cf-update",
    ...
)

static_site_cf.resource.node.add_dependency(api_cf.resource)
```

## Dependencies/Miscellany

In order to support the latest version of the Cloudfront API, this Construct will build a Lambda Layer including the latest version of `boto3`. This requires Docker to be running and will store the layer files in `./cdk.out/layers/cf_update_deps_layer`.

## Forcing updates with a nonce

In the event that it is desirable for the custom resource to run at every deployment, a `nonce` argument can be provided to the construct.  This will trigger the redeployment of the `CustomResource` but not the Lambda or related IAM policies.

```python
from time import time

from constructs import Construct
from cdk_cloudfront_update.constructs import CloudfrontUpdate


class MyApi(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        distribution_arn: str,
        service_path_pattern: str,
        load_balancer_dns_name: str,
        **kwargs,
    ):
        """
        Add MyAPI service to the Cloudfront Distribution at the
        specified path.
        """
        super().__init__(scope, id, **kwargs)

        origin_id = "ApiLoadBalancer"

        CloudfrontUpdate(
            self,
            "my-api-cf-update",
            distribution_arn=distribution_arn,
            behavior_config={
                "PathPattern": service_path_pattern,
                "TargetOriginId": origin_id,
                "TrustedSigners": {"Enabled": False, "Quantity": 0},
                "TrustedKeyGroups": {"Enabled": False, "Quantity": 0},
                "ViewerProtocolPolicy": "redirect-to-https",
                "AllowedMethods": {
                    "Quantity": 7,
                    "Items": [
                        "HEAD",
                        "DELETE",
                        "POST",
                        "GET",
                        "OPTIONS",
                        "PUT",
                        "PATCH",
                    ],
                    "CachedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]},
                },
                "SmoothStreaming": False,
                "Compress": True,
                "LambdaFunctionAssociations": {"Quantity": 0},
                "FunctionAssociations": {"Quantity": 0},
                "FieldLevelEncryptionId": "",
                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",  # Managed CachingDisabled Policy
                "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",  # Managed AllViewer Origin Request Policy
            },
            nonce=str(time())
        )
```
