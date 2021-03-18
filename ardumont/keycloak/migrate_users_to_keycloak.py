# Copyright (C) 2021 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

"""Install deposit users in keycloak instance per realm.

"""

import logging
import click
import yaml

from typing import Dict
from keycloak import KeycloakAdmin


logger = logging.getLogger(__name__)


def create_keycloak_user_dict(user: Dict) -> Dict:
    """Create a mapping dict """
    return {
        "email": user["email"],
        "username": user["username"],
        "firstName": user.get("firstname", ""),
        "lastName": user.get("lastname", ""),
        "credentials": [
            {"value": user["password"], "type": "password", "temporary": False}
        ],
        "enabled": True,
        "emailVerified": False,
    }


@click.command()
@click.option('--server-url', default="http://localhost:5080/keycloak/auth/",
              help="Authentication server")
@click.option('--realm-name', default='SoftwareHeritage',
              help="Authentication realm")
@click.option('--admin-user', help="Admin user")
@click.option('--admin-pass', help="Associated password for admin user")
@click.option('--client-name',
              default="swh-deposit",
              help="Client to associated users to e.g swh-deposit, swh-web, ...")
@click.option('--client-role-name',
              default="swh.deposit.api",
              help="Role to associate to users e.g. swh.deposit.api, ...")
@click.option('--credentials-path', help="YAML credentials file path")
def main(server_url, realm_name, admin_user, admin_pass, client_name, credentials_path, client_role_name):
    """Install deposit users in the keycloak instance

    """
    # Read the credentials file, in yaml format:
    # - username: "user"
    #   password: "pass"
    #   email: "some@email.org"
    # - username: "user2"
    #   password: "pass2"
    #   email: "some2@email.org"
    with open(credentials_path, "r") as f:
        user_creds = yaml.safe_load(f.read())

    keycloak_admin = KeycloakAdmin(server_url, admin_user, admin_pass, realm_name=realm_name)

    # Keycloak information
    client_id = keycloak_admin.get_client_id(client_name)
    user_role = keycloak_admin.get_client_role(client_id, client_role_name)
    logger.info("keycloak server: %s ; realm: %s", server_url, realm_name)
    logger.info("Client: %s ; client role: %s", client_name, client_role_name)

    # Create user and assign them the specific client role name
    for user in user_creds:
        logger.debug("user: %s", user)
        keycloak_user = create_keycloak_user_dict(user)
        user_id = keycloak_admin.create_user(keycloak_user)
        keycloak_admin.assign_client_role(user_id, client_id, user_role)
        logger.info("User '%s' installed.", user["username"])

if __name__ == "__main__":
    logging.basicConfig()
    logger.setLevel("INFO")

    main()
