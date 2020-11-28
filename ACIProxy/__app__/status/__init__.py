import os
import json
import logging

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
        # someone probably deleted container group during run
        return func.HttpResponse(
            body = json.dumps({
                "message": ex.message,
            }),
            headers = {
                "Content-Type": "application/json"
            },
            status_code = 400
        )

    if cg.instance_view.state not in ["Succeeded", "Stopped", "Failed"]:
        return func.HttpResponse(
            body = json.dumps({
                "message": f"Container Group {cg_name} is in progress",
                "name": cg_name,
                "state": cg.instance_view.state
            }),
            headers = {
                "Content-Type": "application/json",
                "Location": f"https://{os.environ['WEBSITE_HOSTNAME']}/api/status/{cg_name}"
            },
            status_code = 202
        )

    else:
        containers = {}

        for container in cg.containers:
            logs = aci_client.containers.list_logs(
                resource_group,
                cg_name,
                container.name
            )

            containers[container.name] = {}
            containers[container.name]["start_time"] = container.instance_view and container.instance_view.current_state.start_time and container.instance_view.current_state.start_time.strftime("%Y-%m-%dT%H:%M:%S")
            containers[container.name]["finish_time"] = container.instance_view and container.instance_view.current_state.finish_time and container.instance_view.current_state.finish_time.strftime("%Y-%m-%dT%H:%M:%S")
            containers[container.name]["state"] = container.instance_view and container.instance_view.current_state.state
            containers[container.name]["exit_code"] = container.instance_view and container.instance_view.current_state.exit_code
            containers[container.name]["detail_status"] = container.instance_view and container.instance_view.current_state.detail_status
            containers[container.name]["output"] = logs.content

        return func.HttpResponse(
            body = json.dumps({
                "message": f"Container Group {cg_name} finished",
                "name": cg_name,
                "state": cg.instance_view.state,
                "containers": containers
            }),
            headers = {
                "Content-Type": "application/json"
            },
            status_code = 200 if cg.instance_view.state == "Succeeded" else 500
        )
