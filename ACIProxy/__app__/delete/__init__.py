import os
import logging
import json
import yaml
import time

import azure.functions as func

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.core.exceptions import AzureError


def main(req: func.HttpRequest) -> func.HttpResponse:

    cg_name = req.route_params.get('cg-name')

    try:
        # tenant_id = os.environ["AZURE_TENANT_ID"]
        # client_id = os.environ["AZURE_CLIENT_ID"]
        # client_secret = os.environ["AZURE_CLIENT_SECRET"]
        subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        resource_group = os.environ["AZURE_RESOURCE_GROUP"]

    except KeyError as ex:
        return func.HttpResponse(
            body=json.dumps({
                "message": "Error loading environment variable: " + str(ex)
            }),
            headers={
                "Content-Type": "application/json"
            },
            status_code=500
        )

    credentials = DefaultAzureCredential()

    aci_client = ContainerInstanceManagementClient(
        subscription_id=subscription_id,
        credential=credentials
    )

    res_client = ResourceManagementClient(
        subscription_id=subscription_id,
        credential=credentials
    )

    try:
        cg = aci_client.container_groups.get(resource_group, cg_name)

    except AzureError as ex:
        # container group not found
        return func.HttpResponse(
            body=json.dumps({
                "message": ex.message,
            }),
            headers={
                "Content-Type": "application/json"
            },
            status_code=400
        )

    aci_client.container_groups.begin_delete(resource_group, cg_name).wait()

    return func.HttpResponse(
        body=json.dumps({
            "message": f"Container Group {cg_name} deleted",
            "name": cg_name
        }),
        headers={
            "Content-Type": "application/json"
        },
        status_code=200
    )
