import os
from typing import Dict, Optional, Sequence
from constructs import Construct
from hashlib import sha256
import json
import docker

from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    custom_resources as cr,
    CustomResource,
    Duration,
)


def generate_name(construct_id: str, name: str):
    return f"{construct_id}-{name}"


class CloudfrontUpdate(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        distribution_arn: str,
        behavior_config: Optional[Dict] = None,
        origin_config: Optional[Dict] = None,
        lambda_execution_policy_statements: Sequence[iam.PolicyStatement] = [],
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        distribution_id = distribution_arn.split(":distribution/")[-1]

        dependencies_layer = self.create_dependencies_layer(
            "cdk.out/layers/cf_update_deps_layer"
        )

        # Cf_Update lambda function
        cf_update_lambda = lambda_.SingletonFunction(
            self,
            generate_name(id, "CFUpdateLambda"),
            uuid="cf-update-lambda",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "./update_cf/"),
            ),
            handler="update_distribution.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            layers=[dependencies_layer],
            timeout=Duration.seconds(60),
        )

        cf_update_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudfront:GetDistributionConfig",
                    "cloudfront:UpdateDistribution",
                ],
                resources=[distribution_arn],
            )
        )

        for statement in lambda_execution_policy_statements:
            cf_update_lambda.add_to_role_policy(statement)

        self.provider = cr.Provider(
            scope,
            generate_name(id, "CFUpdateCustomResourceProvider"),
            on_event_handler=cf_update_lambda,  # type: ignore
        )

        # We add the function version to the Custom Resource properties
        # in order to force a re-run if the function is updated.
        # We do the same with a hash of the provided Policy Statements
        # for the lambda execution role.

        origin_behavior_config = {}
        if behavior_config:
            origin_behavior_config["BehaviorConfig"] = json.dumps(behavior_config)
        if origin_config:
            origin_behavior_config["OriginConfig"] = json.dumps(origin_config)

        self.resource = CustomResource(
            scope=self,
            id=generate_name(id, "CFUpdateResource"),
            service_token=self.provider.service_token,
            properties={
                "Id": distribution_id,
                "FunctionVersion": cf_update_lambda.current_version.version,
                "PolicyStatementHash": sha256(
                    b"\n".join(
                        [
                            json.dumps(statement.to_statement_json()).encode("utf-8")
                            for statement in lambda_execution_policy_statements
                        ]
                    )
                ).hexdigest(),
                **origin_behavior_config,
            },
        )

    def create_dependencies_layer(
        self,
        output_dir: str,
    ) -> lambda_.LayerVersion:
        # Dockerized version of pip install requirements
        client = docker.from_env()

        package_install_dir = os.path.join(output_dir, "python")

        client.containers.run(
            "lambci/lambda:build-python3.8",
            '/bin/sh -c "pip install boto3>=1.26.106 -t /mnt/output/"',
            volumes={
                os.path.abspath(package_install_dir): {
                    "bind": "/mnt/output",
                    "mode": "rw",
                },
            },
        )
        return lambda_.LayerVersion(
            self,
            "CloudfrontUpdateDependencies",
            code=lambda_.Code.from_asset(output_dir),
        )
