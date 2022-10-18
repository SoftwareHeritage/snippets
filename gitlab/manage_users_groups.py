#!/usr/bin/env python3

import logging

import click
import yaml

import gitlab

logger = logging.getLogger(__name__)


@click.command()
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
@click.argument("config_file")
def cli(gitlab_instance, do_it, config_file):
    """Ensure that GitLab users and group memberships match the structure defined in the
    configuration file. This uses the python-gitlab configuration parsing."""
    gl = gitlab.Gitlab.from_config(gitlab_instance)
    gl.auth()

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    if not do_it:
        logger.info(
            "Will not perform any actions, please use --do-it once you're satisfied"
            " with the expected actions."
        )

    for group_path, group_conf in config["groups"].items():
        group = gl.groups.get(group_path, with_projects=False)
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
        for member in group.members.list():
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s:%(levelname)s %(message)s"
    )
    cli()
