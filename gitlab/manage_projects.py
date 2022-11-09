#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import click
import yaml

import gitlab

logger = logging.getLogger(__name__)

Config = Dict[str, Any]


def get_gitlab(gitlab_instance):
    gl = gitlab.Gitlab.from_config(gitlab_instance)
    gl.auth()

    return gl


def update_project(
    project,
    global_settings: Dict[str, Any],
    namespace_settings: Dict[str, Any],
    project_settings: Dict[str, Any],
) -> Tuple:
    """Given a project and settings configuration dicts, update the project.

    Returns:
        Tuple (updated, updated_project). If updated is a dict, then updated_project is
        the project with its attributes updated according to the configuration dicts.
        Otherwise, updated_project is the same instance as 'project' input parameter.

    """
    # override from generic to specific in that order: global -> namespace -> project
    config: Dict[str, Any] = {
        **global_settings,
        **namespace_settings,
        **project_settings,
    }
    logger.debug(
        "Project <%s>: merged configuration: %s", project.path_with_namespace, config
    )

    updated = {}
    # Iterate over the new settings to apply
    for attribute, value in config.items():
        existing_value = getattr(project, attribute)
        # If any changes is detected
        if existing_value != value:
            # New settings is applied
            setattr(project, attribute, value)
            new_value = getattr(project, attribute)
            logger.debug(
                "Update attribute <%s> with value '%s' to value '%s'",
                attribute,
                existing_value,
                new_value,
            )
            updated[attribute] = dict(old=existing_value, new=new_value)

    return updated, project


def load_projects_configuration(projects_file: str) -> Dict[str, Any]:
    """Load the configuration yaml file as Dict."""
    with open(projects_file, "r") as f:
        return yaml.safe_load(f)


def namespaces_from_path(path_with_namespace: str) -> Iterable[str]:
    """Given a path, computes the hierarchic namespaces from generic to specific."""
    namespaces = []
    # FIXME: make that a reduce call!?
    for part in Path(path_with_namespace).parts[:-1]:
        if namespaces:
            last_part = namespaces[-1]
            ns = f"{last_part}/{part}"
        else:
            ns = part
        namespaces.append(ns)

    return namespaces


@click.command()
@click.option(
    "--gitlab",
    "-g",
    "gitlab_instance",
    help="Which GitLab instance to use, as configured in the python-gitlab config",
)
@click.option(
    "--do-it", "do_it", is_flag=True, help="Actually perform the operations",
)
@click.argument("projects_file")
def cli(gitlab_instance: str, do_it: bool, projects_file: str,) -> None:
    gl = get_gitlab(gitlab_instance)

    configuration = load_projects_configuration(projects_file)

    # Global configuration for all projects
    global_settings: Dict[str, Any] = configuration["global_settings"]

    # Namespace project configuration (with possible override on the global config)
    namespace_settings: Dict[str, Any] = configuration["namespace_settings"]

    # List of projects that the script should act upon (other projects are skipped)
    managed_project_namespaces = configuration["managed_project_namespaces"]

    # Local specific project configuration (with possible override on the global config)
    project_settings: Dict[str, Any] = configuration["project_settings"]

    # TODO: Determine whether we want to iterate over all gitlab projects or over the
    # configured projects in the configuration files. For now, this iterates over the
    # gitlab projects and skips non-configured ones. That way, we could discover
    # projects we forgot to configure (by processing the logs afterwards).

    projects: Dict = {}
    project_updated_count = 0

    # Configure the project according to global settings (with potential specific
    # project override)
    for project in gl.projects.list(iterator=True):
        path_with_namespace = project.path_with_namespace
        # For the last print statement to explain how many got updated
        projects[path_with_namespace] = project

        project_namespaces = namespaces_from_path(path_with_namespace)
        if project_namespaces[0] not in managed_project_namespaces:
            logger.debug("Skipped non-managed project <%s>", path_with_namespace)
            continue

        namespace_config = {}
        # Merge configuration from generic namespace to specific
        for ns in project_namespaces:
            namespace_config.update(namespace_settings.get(ns, {}))

        project_config = project_settings.get(path_with_namespace, {})

        logger.debug("Project <%s> %s", path_with_namespace, project.id)
        updates, project = update_project(
            project, global_settings, namespace_config, project_config
        )

        if updates and do_it:
            project.save()
            project_updated_count += 1

        if updates:
            print(json.dumps({path_with_namespace: updates}))

    dry_run = not do_it
    prefix_msg = "(**DRY RUN**) " if dry_run else ""
    summary = {
        "nb_projects": len(projects),
        "nb_updated_projects": project_updated_count,
    }
    if dry_run:
        summary["dry_run"] = dry_run

    logger.debug(
        "%sNumber of projects updated: %s / %s",
        prefix_msg,
        project_updated_count,
        len(projects),
    )

    print(json.dumps(summary))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s:%(levelname)s %(message)s"
    )
    cli(auto_envvar_prefix="SWH")
