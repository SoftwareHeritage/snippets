#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import click
import yaml

import gitlab

logger = logging.getLogger(__name__)


def get_gitlab(gitlab_instance):
    """Instantiate a gitlab instance.

    This uses the python-gitlab configuration parsing.
    """
    gl = gitlab.Gitlab.from_config(gitlab_instance)
    gl.auth()

    return gl


def load_config_file(config_file: str) -> Dict[str, Any]:
    """Load the configuration yaml file as Dict."""
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


@click.group()
@click.option(
    "--gitlab",
    "-g",
    "gitlab_instance",
    help="Which GitLab instance to use, as configured in the python-gitlab config",
)
@click.option(
    "--do-it",
    "do_it",
    is_flag=True,
    help="Actually perform the operations",
)
@click.pass_context
def manage(ctx, gitlab_instance, do_it):
    if not do_it:
        logger.info(
            "Will not perform any actions, please use --do-it once you're satisfied"
            " with the expected actions."
        )

    ctx.ensure_object(dict)
    ctx.obj["gitlab"] = get_gitlab(gitlab_instance)
    ctx.obj["do_it"] = do_it


@manage.command("groups")
@click.argument("config_file")
@click.pass_context
def groups(ctx, config_file):
    """Ensure that GitLab users and group memberships match the structure defined in the
    configuration file."""

    gl = ctx.obj["gitlab"]
    do_it = ctx.obj["do_it"]

    config = load_config_file(config_file)

    config_groups = config.get("groups")
    if not config_groups:
        raise ValueError(
            "Missing config key <groups>, please fill in the configuration file"
        )

    for group_path, group_conf in config_groups.items():
        try:
            group = gl.groups.get(group_path, with_projects=False)
        except gitlab.exceptions.GitlabGetError:
            parent, subgroup = group_path.rsplit("/", 1)
            parent_ns = gl.namespaces.get(parent)
            logger.info(
                "Creating group %s under parent namespace %s", subgroup, parent_ns.name
            )
            if do_it:
                group = gl.groups.create(
                    {
                        "path": subgroup,
                        "name": group_conf.get("name", subgroup),
                        "parent_id": parent_ns.id,
                    }
                )
            else:
                continue

        expected_members = {
            username: gitlab.const.AccessLevel[access_level.upper()]
            for username, access_level in group_conf["users"].items()
        }
        recorded_members = set()

        expected_group_shares = {
            other_path: gitlab.const.AccessLevel[access_level.upper()]
            for other_path, access_level in group_conf.get(
                "share_with_groups", {}
            ).items()
        }
        recorded_members = set()

        remove_extra_memberships = group_conf.get("remove_extra_memberships", False)
        for member in group.members.list(get_all=True):
            username = member.username
            expected_access_level = expected_members.get(member.username)
            if expected_access_level and member.access_level != expected_access_level:
                logger.info(
                    "Adjusting membership for %s in %s to %s (was %s)",
                    username,
                    group_path,
                    expected_access_level.name,
                    member.access_level,
                )
                if do_it:
                    member.access_level = expected_access_level
                    member.save()

            if remove_extra_memberships and not expected_access_level:
                logger.info("Removing member %s from %s", username, group_path)
                if do_it:
                    member.delete()

            recorded_members.add(username)

        for username, access_level in expected_members.items():
            if username in recorded_members:
                continue

            users = gl.users.list(username=username)
            if not users:
                logger.warning(
                    "User %s not found, cannot add them to %s!", username, group_path
                )
                continue

            user_id = users[0].id

            logger.info(
                "Adding member %s in %s at level %s", username, group_path, access_level
            )
            if do_it:
                group.members.create({"user_id": user_id, "access_level": access_level})

        recorded_group_shares = set()

        for group_share in group.shared_with_groups:
            other_path = group_share["group_full_path"]
            other_id = group_share["group_id"]
            other_access_level = group_share["group_access_level"]
            expected_access_level = expected_group_shares.get(other_path)
            if expected_access_level and other_access_level != expected_access_level:
                logger.info(
                    "Adjusting group_share for %s in %s to %s (was %s)",
                    other_path,
                    group_path,
                    expected_access_level,
                    other_access_level,
                )
                if do_it:
                    group.share(other_id, expected_access_level)

            if remove_extra_memberships and not expected_access_level:
                logger.info("Removing group %s from %s", other_path, group_path)
                if do_it:
                    group.unshare(other_id)

            recorded_group_shares.add(other_path)

        for other_path, access_level in expected_group_shares.items():
            if other_path in recorded_group_shares:
                continue

            other_group = gl.groups.get(other_path)
            if not other_group:
                logger.warning(
                    "Group %s not found, cannot add them to %s!", other_path, group_path
                )
                continue

            logger.info(
                "Adding group %s in %s at level %s",
                other_path,
                group_path,
                access_level,
            )
            if do_it:
                group.share(other_group.id, access_level)


def update_project(
    project,
    global_settings: Dict[str, Any],
    namespace_settings: Dict[str, Any],
    project_settings: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Any, Optional[bool]]:
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
    archive_project: Optional[bool] = None
    # Iterate over the new settings to apply
    for attribute, value in config.items():
        existing_value = getattr(project, attribute)
        # If any changes is detected
        if existing_value != value:
            if attribute == "archived":
                if value:
                    logger.debug("archive project")
                else:
                    logger.debug("unarchive project")
                archive_project = value
                continue
            # New settings is applied
            setattr(project, attribute, value)
            new_value = getattr(project, attribute)
            logger.debug(
                "Update attribute <%s> with value '%s' to value '%s'",
                attribute,
                existing_value,
                new_value,
            )
            updated[attribute] = {"old": existing_value, "new": new_value}

    return updated, project, archive_project


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


@manage.command("projects")
@click.argument("config_file")
@click.argument("project_list", nargs=-1, required=False)
@click.pass_context
def projects(
    ctx,
    config_file: str,
    project_list: List[str],
) -> None:
    gl = ctx.obj["gitlab"]
    do_it = ctx.obj["do_it"]

    config = load_config_file(config_file)

    config_projects = config.get("projects")
    if not config_projects:
        raise ValueError(
            "Missing config key <projects>, please fill in the configuration file"
        )

    # Global configuration for all projects
    global_settings: Dict[str, Any] = config_projects["global_settings"]

    # Namespace project configuration (with possible override on the global config)
    namespace_settings: Dict[str, Any] = config_projects["namespace_settings"]

    # List of projects that the script should act upon (other projects are skipped)
    managed_project_namespaces = config_projects["managed_namespaces"]

    # Local specific project configuration (with possible override on the global config)
    project_settings: Dict[str, Any] = config_projects["project_settings"]

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
        if project_list and not path_with_namespace.startswith(project_list):
            continue
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

        updates, project, archive_project = update_project(
            project, global_settings, namespace_config, project_config
        )

        if "shared_with_groups" in updates:
            s = updates.pop("shared_with_groups")
            old = s["old"]
            new = s["new"]
            old_paths = set(g["group_full_path"] for g in old)
            for group_path in set(new) - old_paths:
                group = gl.groups.get(group_path, with_projects=False)
                logger.info(
                    "Sharing project %s with group %s", path_with_namespace, group_path
                )
                if do_it:
                    project.share(
                        group_id=group.id, group_access=40
                    )  # Hardcoded to maintainer

        if updates and do_it:
            project.save()
            project_updated_count += 1

        if updates:
            print(json.dumps({path_with_namespace: updates}))

        if archive_project is not None:
            if archive_project:
                logger.info("Archiving project %s", path_with_namespace)
                if do_it:
                    project.archive()
            else:
                logger.info("Unarchiving project %s", path_with_namespace)
                if do_it:
                    project.unarchive()

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
    manage(auto_envvar_prefix="SWH")
