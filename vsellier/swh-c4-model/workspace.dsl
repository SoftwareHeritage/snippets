workspace {

    model {
        user = person "Internet User" {
          tags scn, vault
        }
        depositUser = person "Deposit Partners" {
          tags deposit
        }
        scanner = person "Scanner" {
          tags scanner,provenance
        }

        codeOwner = person "Code owner" {
          tags tdn
        }

        systemAdministrator = person "SWH Sysadmin" {
          tags tdn
        }

        forge = softwareSystem "External Forge" {
          tags "external"
        }

        dpo = person "DPO" {
          tags tdn
        }

        inriaEmailRelay = softwareSystem "Email relay" {
          tags  external,deposit
        }

        swh = softwareSystem "Software Heritage" {
          keycloak = container "keycloak" "" """provenance"

          alter = container "swh-alter" {
            tags tdn

            alter_cli = component "cli" {
              technology "python"
              tags cli
            }

            alter_recovery_bundle = component "Recovery_bundle" {
              technology "ZIP file"
              tags file
            }
          }

          deposit = container "Deposit"

          elasticsearch = container "Elasticsearch" {
            tags search, db
          }

          graph_rpc = container "graph rpc" {
            technology python
            tags "tdn"
          }
          graph_grpc = container "swh-graph grpc" {
            technology "java/rust"
            tags provenance,tdn
          }

          lister = container "listers"

          loader = container "loaders" {
            tags scn
          }

          masking_proxy_db = container "masking-proxy-db" {
            tags db
            technology "Postgresql"
          }

          provenance_rpc = container "swh-provenance-rpc" {
            technology python
            tags provenance
          }

          rabbitmq = container "RabbitMQ" {
            tags scn,queue
          }

          scheduler = container "scheduler" {
            tags scn

            scheduler_rpc = component "RPC API"
            scheduler_runner = component "scheduler runner"
            scheduler_listener = component "scheduler listerner"
            scheduler_journal_client = component "journal client"

            scheduler_db = component "Scheduler database" {
              technology "Postgresql"
              tags db
            }
          }


          storage_rpc = container "storage-rpc" {
            tags scn,tdn

            technology "python"
          }

          storage_db = container "storage-db" {
            technology "postgresql or cassandra"
          }


          storage = container "swh-storage" {
            tags scn,tdn


            masking_proxy = component "masking-proxy" {
              technology "python"
            }

            masking_proxy_cli = component "masking-proxy-cli" {
              technology "python"
            }

            blocking_proxy = component "blocking-proxy" {
              technology "python"
            }

            blocking_proxy_cli = component "blocking-proxy-cli" {
              technology "python"
            }

            blocking_proxy_db = component "blocking-proxy database" {
              tags db
              technology "Postgresql"
            }

          }

          search = container "swh-search" {
            tags scn,tdn

            search_journal_client = component "search-journal-client" {
              technology "python"

              tags "journal-client,"
            }

            search_rpc = component "search-rpc" {
              technology "python"
            }
          }

          kafka = container "Kafka Journal" {
            tags scn,queue
          }

          objstorage = container "swh-objstorage" {
            tags tdn

            objstorage_rpc = component "objstorage-rpc"
            path_slicing = component "pathslicing" {
              tags file
            }
            winery_db = component "winery_db" {
              technology Postgresql
              tags "db"
            }
            objstorage_bucket = component "S3/AWS buckets" {
              technology "https"
              tags "db"
            }
            objstorage_replayer = component "replayer" {
              technology "python"
              tags "replayer"
            }
          }

          vaultAzureBucket = container "Vault Azure Object Storage" {
            tags vault
          }

          vault = container "vault" {
            vault_rpc = component "swh-vault rpc" {
              technology python
            }

            vault_cookers = component "swh-vault cooker" {
              technology python
            }
          }

          webapp = container "Webapp" {
            tags scn, vault, provenance
          }

        }

        // Global use cases
        user -> swh "Browses an origin\nAsks to retreive an origin content"
        user -> keycloak "Creates and manage an account"
        systemAdministrator -> keycloak "Manages user permission"

        // storage
        storage_rpc -> storage_db "reads and writes graph" "sql or cql"
        storage_rpc -> kafka "pushes messages" "tcp" "tdn"
        storage_rpc -> kafka "removes messages" "tcp" "tdn"
        storage_rpc -> objstorage_rpc "adds contents" "" "tdn"
        storage_rpc -> masking_proxy "Filters names and objects" "tdn"
        storage_rpc -> blocking_proxy "Checks blocked objects " "tdn"
        storage_rpc -> masking_proxy_db "CRUDs" "tdn"
        storage_rpc -> blocking_proxy_db "CRUDS" "tdn"

        // Save Code Now
        user -> webapp "ask for a save code now" "" "scn"
        webapp -> scheduler_rpc "uses" "RPC" "scn"
        scheduler -> rabbitmq "posts a message" "celery" "scn,vault"
        loader -> rabbitmq "handles a task" "celery" "scn"
        loader -> storage "store the repository" "rpc" "scn"
        storage -> kafka "write the objects" "tcp" "scn"

        // Vault
        user -> webapp "asks for a repository cooking" "" "vault"
        webapp -> inriaEmailRelay "notififies a user that a bundle is ready" "" "vault"
        inriaEmailRelay -> user "sends emails" "" "vault"
        user -> vaultAzureBucket "download a bundle" "" "vault"

        webapp -> vault_rpc "Creates a vault cooking" "" "vault"
        vault_rpc -> scheduler "Creates a cooking task" "" "vault"
        vault_rpc -> objstorage_rpc "???" "rpc" "to_check,vault"
        vault_rpc -> storage_rpc "???" "rpc" "to_check,vault"
        vault_cookers -> rabbitmq "Gets a cooking task" "" "vault"
        vault_cookers -> graph_rpc "Asks the swhid to cook" "rpc" "to_check,vault"
        vault_cookers -> storage_rpc "???" "rpc" "to_check,vault"
        vault_cookers -> vault_rpc "Sends the bundle" "" vault"
        vault_rpc -> vaultAzureBucket "Stores the bundle" "" "vault"

        // scheduler
        scheduler_runner -> rabbitmq "posts tasks" "celery"
        scheduler_runner -> scheduler_rpc "selects origins to schedule" "sql"
        scheduler_journal_client -> kafka "reads messages" "tcp"
        scheduler_rpc -> scheduler_db "reads and Writes" "sql"
        scheduler_listener -> scheduler_rpc "updates task status"
        scheduler_listener -> rabbitmq "listens to notifications" "celery"
        scheduler_journal_client -> scheduler_rpc "updates origin status"

        webapp -> scheduler "schedules an high priority"
        webapp -> user "notifies an origin content is ready to be downloaded" {
          tags deposit
        }
        webapp -> search_rpc "search for origins"
        webapp -> graph_rpc "Proxifies graph api requests" "rpc"
        webapp -> storage_rpc "requests"

        scheduler -> rabbitmq "posts messages"

        // deposit
        depositUser -> swh "Deposits code and get origin contents"
        depositUser -> deposit "deposits code"
        depositUser -> webapp "displays swhid details" "https/iframes"

        // graph
        graph_rpc -> graph_grpc "Requests" "grpc" "graph"
        graph_rpc -> graph_grpc "Starts" "grpc" "graph"

        // search
        search_journal_client -> kafka "reads messages" "tcp" "tdn,search"
        search_journal_client -> search_rpc "gets, upserts or deletes origins and metadata" "rpc" "tdn, search"
        search_rpc -> elasticsearch "get, upserts or deletes documents" "http" "search,tdn"

        // objstorage
        objstorage_replayer -> objstorage_rpc "replays content"
        objstorage_replayer -> objstorage_bucket "replays content"

        // provenance
        scanner -> webapp "Sends authenticated requests" "rpc" "provenance" {
            properties {
              role "XXXXX"
            }
        }
        webapp -> provenance_rpc "Sends requests" "grpc" "provenance,,overlapped" {
        }

        provenance_rpc -> graph_grpc "Sends requests" "grpc" "provenance,overlapped"

        // alter/takedown
        codeOwner -> dpo "requests a takedown or a name change" "" "tdn"
        dpo -> systemAdministrator "notifies of a takedown to proceed" "" "tdn"
        dpo -> webapp "adds an entry in the mailmap" "" "tdn"
        webapp -> masking_proxy_db "Refreshes masking and mailmap information"

        systemAdministrator -> swh "proceeds a take down request""" "tdn"
        systemAdministrator -> alter_cli "launchs a takedown of an origin" "cli" "tdn"
        systemAdministrator -> blocking_proxy_cli "Manages blocked objects" "cli" "tdn"
        systemAdministrator -> masking_proxy_cli "Manages masked objects" "cli" "tdn"

        alter_cli -> graph_rpc "gets the objects related to an origin" "rpc" "tdn"
        alter_cli -> storage_rpc "gets the recent objects related to an origin \n removes objects \n restores objects" "rpc" "tdn"
        alter_cli -> alter_recovery_bundle "saves to" "" "tdn"
        alter_cli -> alter_recovery_bundle "restores from" "" "tdn"
        alter_cli -> kafka "removes objects" "tcp""tdn"
        alter_cli -> objstorage_rpc "removes contents" "rpc" "tdn"
        alter_cli -> search_rpc "removes origins" "rpc" "tdn"

        swh -> forge "gets repository list and contents"

        loader -> forge "gets a repository"
        lister -> forge "gets available repositories"

        webapp -> keycloak "gets authenticated user roles" "" "provenance,overlapped"

        staging = deploymentEnvironment "Staging" {
          pg = deploymentGroup "Postgresql"
          cassandra = DeploymentGroup "Cassandra"

          deploymentNode "rp0" {
              stg_hitch = infrastructureNode "hitch" {
                description "ssl termination"
              }
              stg_varnish = infrastructureNode "varnish" {
                description "cache and reverse-proxy"
              }
              stg_hitch -> stg_varnish ""
          }

          deploymentNode "kelvingrove" {
            dep_stg_keycloak = containerInstance "keycloak" "cassandra,pg" "provenance"
          }

          archive_staging_rke2 = deploymentNode "archive-staging-rke2" {
            tags ""
            deploymentNode "swh" {
              tags "Kubernetes - ns"

              deploymentNode "storage_ingress" {
                tags "Kubernetes - ing"

                containerInstance "storage_rpc" "pg" {
                  tags "Kubernetes - dep"
                  description "ro-storage"
                }
              }
              deploymentNode "archive-webapp-ingress" {
                tags "Kubernetes - ing"

                url "http://webapp-postgresql.internal.staging.swh.network"

                containerInstance "webapp" "pg" {
                  tags "Kubernetes - dep"
                  description "archive webapp"
                  tags provenance
                }
              }

            }

            deploymentNode "swh-cassandra" {
              tags "Kubernetes - ns"

              stg_graph_dep = deploymentNode "graph"{
                tags "Kubernetes - deploy"
                containerInstance graph_rpc "cassandra"
                containerInstance graph_grpc "cassandra"
              }

              stg_persistent_node_vol = infrastructureNode "graph_persistent_vol" {
                tags "Kubernetes - pv,db"
              }
              stg_inmemory_node_vol = infrastructureNode "graph_inmemory_vol" {
                tags "Kubernetes - pv,db"
              }
              stg_graph_dep -> stg_persistent_node_vol "Uses" "fs" "graph"
              stg_graph_dep -> stg_inmemory_node_vol "Uses"  "fs" "graph"
              stg_inmemory_node_vol -> stg_persistent_node_vol "links"

              containerInstance "storage_rpc" "cassandra" {
                  tags "Kubernetes - deploy"
              }
              deploymentNode "provenance-ingress" {
                tags "Kubernetes - ing"
                url "http://provenance-local"

                containerInstance "provenance_rpc" "cassandra,pg" {
                  tags "Kubernetes - deploy"
                }
              }

              deploymentNode "archive-webapp-ingress" {
                tags "Kubernetes - ing"
                url "http://webapp.staging.swh.network,http://webapp-cassandra.internal.staging.swh.network"

                containerInstance "webapp" "cassandra" {
                  tags "Kubernetes - deploy"
                  description "archive webapp"
                }
              }
              containerInstance "webapp" "cassandra" {
                tags "Kubernetes - deploy"

                description "webhook webapp"
              }
              containerInstance "storage_rpc" "cassandra" {
                tags "Kubernetes - deploy"

                description "rw-db1"
              }

            }
          }

          deploymentNode "db1" {
            tags "db"
            deploymentNode "postgres:5432" {
              containerInstance "storage_db" "pg" "db"
              containerInstance "masking_proxy_db" "pg,cassandra" "db"
            }
          }
          deploymentNode "cassandra cluster" {
            tags db
            containerInstance "storage_db" "cassandra" "db"
          }

          stg_varnish -> "archive_staging_rke2" ""
        }

        production = deploymentEnvironment "Production" {
          deploymentNode "moma" {
              prd_hitch = infrastructureNode "hitch" {
                description "ssl termination"
              }
              prd_varnish = infrastructureNode "varnish" {
                description "cache and reverse-proxy"
              }
              prd_hitch -> prd_varnish ""
          }

          deploymentNode "kelvingrove" {
            containerInstance "keycloak" "cassandra,pg" "provenance"
          }

          deploymentNode "granet" {
            containerInstance "graph_grpc" "cassandra,pg" "provenance"
          }

          archive_production_rke2 = deploymentNode "archive-production-rke2" {
            deploymentNode "swh" {
              tags "Kubernetes - ns"

              deploymentNode "storage_ingress" {
                tags "Kubernetes - ing"

                containerInstance "storage_rpc" "pg" {
                  description "ro-storage"
                }
                containerInstance "storage_rpc" "pg" {
                  description "rw-storage"
                }
              }
              deploymentNode "webapp_ingress" {
              tags "Kubernetes - ing"
                containerInstance "webapp" "pg" {
                  description "archive webapp"
                }
              }
            }

            deploymentNode "provenance-ingress" {
              tags "Kubernetes - ing"
              url "http://provenance-local"
              description "http://provenance-local"

              containerInstance "provenance_rpc" "cassandra,pg"
            }
          }

          deploymentNode "swh-cassandra" {
            tags "Kubernetes - ns"

            deploymentNode "storage_ingress" {
              tags "Kubernetes - ing"

              containerInstance "storage_rpc" "cassandra" {
                description "ro-storage"
              }
              containerInstance "storage_rpc" "cassandra" {
                description "rw-storage"
              }
            }

            deploymentNode "webapp_ingress" {
              tags "Kubernetes - ing"

              containerInstance "webapp" "cassandra" {
                description "archive webapp"
              }
            }
          }

          prd_varnish -> "archive_production_rke2" ""

        }


    }

####################################################################################################
    views {

        theme "https://static.structurizr.com/themes/kubernetes-v0.3/theme.json"


        deployment * staging "staging_provenance" {
            title "swh-provenance Staging deployment"
            include "element.tag==provenance"
            autolayout

        }

        deployment * production "production_provenance" {
            include "element.tag==provenance"
            autolayout
        }


        deployment * staging "global_staging_view"{
            include "*"
            autolayout
        }

        deployment * production "global_production_view" {
            include "*"
            autolayout
        }


        systemContext swh {
            include *
            autolayout
        }

        container swh "global" {
          include *
          autolayout
        }

        container swh "storage" {
          include "->storage_rpc->"
          autoLayout
        }

        component storage "storage_components" {
          include *
          autoLayout
        }

        container swh "scheduler" {
          include "->scheduler->"
          autoLayout
        }

        component search "search" {
          include *
          autoLayout
        }


        component scheduler "scheduler_components" {
          include *
          autoLayout
        }

        // container swh "global" {
        //   include *
        //   autolayout lr
        // }

        container swh "Save_Code_Now" {
          include "element.tag==scn"
          exclude "relationship.tag!=scn"
          autolayout
        }

        container swh "swh-alter" {
          include "element.tag==tdn"
          exclude "relationship.tag!=tdn"
          autolayout
        }

        component alter "swh-alter_components" {
          include *
          exclude "relationship.tag!=tdn"
          autolayout
        }

        container swh "swh-graph_components" {
          include ->graph_rpc-> ->graph_grpc->
          autolayout
        }

        container swh "vault" {
          include "->vault->"
          autolayout
        }

        component vault "vault_components" {
          include *
          exclude "relationship.tag!=vault"
          autolayout
        }

        container swh "provenance" {
          include "element.tag==provenance"
          exclude "relationship.tag!=provenance"
          autolayout lr
        }


      styles {
        element "Person" {
          shape person
          color white
          background blue
        }
        element "queue" {
          shape pipe
        }
        element "db" {
          shape cylinder
        }
        element "softwareSystem" {
          background indianred
        }
        element "deploymentNode" {
          shape circle
          description true
          metadata true
        }
        element "external" {
          background darkseagreen
        }
        element "file" {
          shape Folder
          background lightgreen
        }
        relationship overlapped {
          position 75
        }

      }

    }


}
