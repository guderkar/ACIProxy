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
    polling_param = req.params.get("polling")
    polling = True if (polling_param != None and polling_param.lower() == "true") else False

    try:
        body_yaml = req.get_body().decode("utf-8")
        cg_definition = yaml.safe_load(body_yaml)

    except BaseException as ex:
        return func.HttpResponse(
            body=json.dumps({
                "message": "Error while parsing yaml:\n\n" + str(ex)
            }),
            headers={
                "Content-Type": "application/json"
            },
            status_code=400
        )

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

    cg_name = cg_definition.get('name', None)
    location = cg_definition.get('location', None) or res_client.resource_groups.get(resource_group).location
    api_version = cg_definition.get('apiVersion', None) or aci_client._config.api_version
    cg_definition['location'] = location
    cg_definition['apiVersion'] = api_version

    if cg_name == None:
        return func.HttpResponse(
            body=json.dumps({
                "message": "Name property missing in yaml definition"
            }),
            headers={
                "Content-Type": "application/json"
            },
            status_code=400
        )

    try:
        cg = aci_client.container_groups.get(resource_group, cg_name)

        if cg.instance_view.state not in ["Succeeded", "Stopped", "Failed"]:
            # Container Group already running
            return func.HttpResponse(
                body=json.dumps({
                    "message": f"Container Group {cg_name} is already running",
                    "name": cg_name,
                    "state": cg.instance_view.state
                }),
                headers={
                    "Content-Type": "application/json"
                },
                status_code=400
            )

    except AzureError:
        # container group not found, thats fine
        pass


    try:
        # create or update container group
        res_client.resources.begin_create_or_update(
            resource_group_name=resource_group,
            resource_provider_namespace="Microsoft.ContainerInstance",
            parent_resource_path="",
            resource_type="containerGroups",
            resource_name=cg_name,
            api_version=api_version,
            parameters=cg_definition
        )

        # start container group and wait until it's truly started
        aci_client.container_groups.begin_start(resource_group, cg_name)
        cg = aci_client.container_groups.get(resource_group, cg_name)

        while cg.instance_view.state not in ["Pending", "Running"]:
            aci_client.container_groups.begin_start(resource_group, cg_name)
            cg = aci_client.container_groups.get(resource_group, cg_name)
            time.sleep(5)

    except AzureError as ex:
        return func.HttpResponse(
            body=json.dumps({
                "message": ex.message
            }),
            headers={
                "Content-Type": "application/json"
            },
            status_code=400
        )

    # redirect client to status function
    if polling == True:
        return func.HttpResponse(
            body=json.dumps({
                "message": f"Container Group {cg_name} started",
                "name": cg_name,
                "state": cg.instance_view.state
            }),
            headers={
                "Content-Type": "application/json",
                "Location": f"https://{os.environ['WEBSITE_HOSTNAME']}/api/status/{cg_name}"
            },
            status_code=202
        )

    # just return success
    else:
        return func.HttpResponse(
            body=json.dumps({
                "message": f"Container Group {cg_name} started",
                "name": cg_name,
                "state": cg.instance_view.state
            }),
            headers={
                "Content-Type": "application/json"
            },
            status_code=200
        )
