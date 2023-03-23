#!/usr/bin/env python3

# Copyright (C) The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import click
import keycloak


@click.command()
@click.option(
    "--keycloak-server-url",
    default="https://auth.softwareheritage.org/auth/",
    show_default=True,
    help="Keycloak server URL",
)
@click.option(
    "--realm-name",
    default="SoftwareHeritage",
    show_default=True,
    help="Name of the realm to count registered users",
)
@click.option(
    "--admin-username",
    help="Username for an user with administration rights on the realm",
    required=True,
)
@click.option(
    "--admin-password",
    help="Password for the user with administration rights on the realm",
    required=True,
)
@click.pass_context
def run(ctx, keycloak_server_url, realm_name, admin_username, admin_password):
    """Count the users registered in a Keycloak realm."""

    keycloak_admin = keycloak.KeycloakAdmin(
        server_url=keycloak_server_url,
        username=admin_username,
        password=admin_password,
        realm_name=realm_name,
    )

    users = keycloak_admin.get_users()

    print(
        f"{len(users)} registered in realm {realm_name} for keycloak instance "
        f"located at {keycloak_server_url}"
    )


if __name__ == "__main__":
    run()
