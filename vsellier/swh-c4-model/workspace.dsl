workspace {

    model {
        user = person "Internet User" {
          tags scn, vault
        }
        depositUser = person "Deposit Partners" {
          tags deposit,citation
        }
        scanner = person "Scanner" {
          tags scanner,provenance
        }

        codeOwner = person "Code owner" {
          tags tdn
        }

        fairCorePartners = person "FairCore Partners" {
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

        mirrors = softwareSystem "SWH mirrors" {
          tags  external,mirrors
        }

        inriaEmailRelay = softwareSystem "Email relay" {
          tags  external,deposit
        }

        swh = softwareSystem "SoftwareHeritage" {
          !decisions docs/coarnotify/adrs
          keycloak = container "keycloak" "" "provenance,provenance_v2"

          gitlab = container "Gitlab" {
            tags  external,add-forge-now
          }

          group swh-coarnotify {
            coarnotify_rpc = container "coarnotify-rpc" {
              !docs docs/coarnotify
              !decisions docs/coarnotify/adrs
              technology django
            }
            coarnotify_db = container "coarnotify-db" {
              technology PostgreSQL
            }
          }

          group swh-provenance {
            provenance-grpc = container "provenance-grpc" {
              !docs docs/provenance-v0.3
              !decisions docs/provenance-v0.3/adrs
              technology rust,parquet
            }
          }

          alter = container "swh-alter" {
            tags tdn,search

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

          graph_rpc = container "graph rpc" {
            technology python
            tags "tdn"
          }

          graph_grpc = container "swh-graph grpc" {
            technology "java/rust"
            tags "provenance_v2,tdn"
          }

          lister = container "listers"

          loader = container "loaders" {
            tags scn
          }

          provenance_rpc = container "swh-provenance-rpc" {
            technology python
            tags provenance_v2
          }

          provenance_grpc = container "swh-provenance-grpc" {
            technology rust
            tags "provenance_v2,provenance"
          }

          provenance_parquet_files = container "swh-parquet-files" {
            technology rust
            tags provenance,parquet
          }

          rabbitmq = container "RabbitMQ" {
            tags scn,queue
          }

          scheduler = container "scheduler" {
            tags scn

            scheduler_rpc = component "RPC API"
            scheduler_runner = component "scheduler runner (lister, addforgenow, cook, deposit)"
            scheduler_runner_priority = component "scheduler runner priority (save-code-now)"
            scheduler_schedule_recurrent = component "scheduler of recurrent origins to load"
            scheduler_listener = component "scheduler listener"
            scheduler_journal_client = component "journal client"

            scheduler_db = component "Scheduler database" {
              technology "Postgresql"
              tags db
            }
          }

          group storage {
            storage_rpc = container "storage-rpc" {
              tags scn,tdn,citation

              technology "python"

              masking_proxy = component "masking-proxy" {
                technology "python"

                description "Filters names and objects"
              }

              blocking_proxy = component "blocking-proxy" {
                technology "python"

                description "Checks blocked objects"
              }
            }
            blocking_proxy_cli = container "blocking-proxy-cli" {
              technology "python"
            }

            masking_proxy_cli = container "masking-proxy-cli" {
              technology "python"
            }

            storage_db = container "storage-db" {
              technology "postgresql or cassandra"
            }

            blocking_proxy_db = container "blocking-proxy database" {
              tags db
              technology "Postgresql"
            }

            masking_proxy_db = container "masking-proxy-db" {
              tags db
              technology "Postgresql"
            }

          }

          group indexer {
            indexer_storage_rpc = container "indexer-storage-rpc" "" {
              technology "python"
              tags "citation"
            }

            indexer_db = container "indexer-db" "" "" {
              technology "postgresql"
              tags "db"
            }
            indexer_metadata = container "metadata-indexer" "" "" {
              technology "python"
              tags "service"
            }
          }

          group "swh-search" {
            // tags scn,tdn

            search_journal_client = container "search-journal-client" {
              technology "python"

              tags "journal-client,tdn,search"
            }

            search_rpc = container "search-rpc" {
              technology "python"
              tags search
            }

            elasticsearch = container "Elasticsearch" {
              tags search, db
            }
          }

          kafka = container "Kafka Journal" {
            tags scn,queue,search
          }

          group "objstorage" {

            objstorage_rpc = container "objstorage-rpc"
            path_slicing = container "pathslicing" {
              tags file
            }
            winery = container "winery" {
              technology Postgresql
              tags "db"
            }
            objstorage_bucket = container "S3/AWS buckets" {
              technology "https"
              tags "db"
            }
            objstorage_replayer = container "replayer" {
              technology "python"
              tags "replayer"
            }
          }

          vaultAzureBucket = container "Vault Azure Object Storage" {
            tags vault
          }

          vault = container "vault" {
            vault_rpc = component "vault rpc" {
              technology python
            }

            vault_cookers = component "swh-vault cooker" {
              technology python
            }
          }

          webapp = container "Webapp" {
            tags scn, vault, provenance, provenance_v2, citation,search, add-forge-now
          }

          group "winery" {
            winery_db = container "winery database" "PostgreSQL" ""
            winery_rpc = container "winery rpc" "python" {
              description "objstorage RPC implementation"
            }
            winery_shard_cleaner = container "winery shard cleaner" "python"
            winery_shard_packer = container "winery shard packer" "python"
            winery_rbd = container "winery rbd image manager" "python"
            winery_os =  container "OS" "Linux" {
              tags system
            }
          }

          ceph = container "ceph storage" "ceph"

          winery_rpc -> winery_db "Adds and gets contents"
          winery_shard_packer -> winery_db "Reads shards content"
          winery_shard_packer -> ceph "Stores shards content"
          winery_rbd -> winery_db "Reads shard statuse" "sql"
          winery_rbd -> winery_os "Mounts ceph rbd image" "shell"
          winery_os -> ceph "Exposes ceph rbd image" "fuse"
          winery_shard_cleaner -> winery_db "Removes packed and mounted shards"
          storage_rpc -> winery_rpc "Adds and gets contents" "http"
          objstorage_replayer -> winery_rpc "Adds content"
        }


        // Global use cases
        user -> swh "Browses an origin\nAsks to retreive an origin content"
        user -> keycloak "Creates and manage an account"
        systemAdministrator -> keycloak "Manages user permission"

        // Add-Forge-Now
        user -> webapp "Asks for a add forge now" "" "add-forge-now"
        systemAdministrator -> webapp "Validate an add forge request" "" "add-forge-now"
        webapp -> gitlab "triggers add-forge-now pipeline" "https" "add-forge-now"
        gitlab -> scheduler "Registers lister / Schedules listing and visits" "cli" "add-forge-now"
        gitlab -> scheduler "Check listed and visited origins" "cli"

        // Citation
        depositUser -> webapp "Asks for a citation" "https" "citation"
        webapp -> indexer_storage_rpc "converts metadata to bibtex" "django" "citation"
        webapp -> storage_rpc "gets SWHid metatadata" "http" "citation"

        // Coar notify
        fairCorePartners -> coarnotify_rpc "sends a notifications" "" "http"
        coarnotify_rpc -> fairCorePartners "sends an acknoledgment and information" "" "http"
        coarnotify_rpc -> coarnotify_db "Stores messages" "" "SQL"
        coarnotify_rpc -> storage_rpc "Stores raw_extrinsic_metadata" "" "http"

        // deposit
        depositUser -> swh "Deposits code and get origin contents"
        depositUser -> deposit "deposits code"
        depositUser -> webapp "displays swhid details" "https/iframes"

        // graph
        graph_rpc -> graph_grpc "Requests" "grpc" "graph"
        graph_rpc -> graph_grpc "Starts" "grpc" "graph"

        // indexer
        indexer_storage_rpc -> indexer_db "reads and writes content metadata" "sql"

        // mirrors
        mirrors -> kafka "follows objects stream" "kafka"
        mirrors -> objstorage_bucket "gets object content" "https"

        // Save Code Now
        user -> webapp "Asks for a save code now" "" "scn"
        webapp -> scheduler_rpc "uses" "RPC" "scn"
        scheduler -> rabbitmq "posts a message" "celery" "scn,vault"
        loader -> rabbitmq "handles a task" "celery" "scn"
        loader -> storage_rpc "store the repository" "rpc" "scn"
        storage_rpc -> kafka "write the objects" "tcp" "scn"

        // storage
        storage_rpc -> storage_db "reads and writes graph" "sql or cql"
        storage_rpc -> kafka "pushes messages" "tcp" "tdn"
        storage_rpc -> kafka "removes messages" "tcp" "tdn"
        storage_rpc -> objstorage_rpc "adds contents" "" "tdn"
        # storage_rpc -> masking_proxy "Filters names and objects" "t dn"
        # storage_rpc -> blocking_proxy "Checks blocked objects" "tdn"
        # storage_rpc -> masking_proxy_db "CRUDs" "tdn"
        storage_rpc -> blocking_proxy_db "CRUDS" "tdn"
        indexer_metadata -> kafka "reads raw_extrinsic_metadata" "kafka"

        // scheduler
        scheduler_runner -> rabbitmq "posts tasks" "celery"
        scheduler_runner -> scheduler_rpc "selects tasks to schedule" "sql"
        scheduler_runner_priority -> rabbitmq "posts tasks" "celery"
        scheduler_runner_priority -> scheduler_rpc "selects tasks to schedule" "sql"
        scheduler_schedule_recurrent -> rabbitmq "posts tasks" "celery"
        scheduler_schedule_recurrent -> scheduler_rpc "selects origins to schedule" "sql"
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
        vault_cookers -> storage_rpc "Retrieves data to cook" "rpc" "to_check,vault"
        vault_cookers -> vault_rpc "Sends the bundle" "" "vault"
        vault_rpc -> vaultAzureBucket "Stores the bundle" "" "vault"

        // search
        search_journal_client -> kafka "reads messages" "tcp" "tdn,search"
        search_journal_client -> search_rpc "gets, upserts or deletes origins and metadata" "rpc" "tdn, search"
        search_rpc -> elasticsearch "get, upserts or deletes documents" "http" "search,tdn"

        // objstorage
        objstorage_replayer -> objstorage_rpc "replays content"
        objstorage_replayer -> objstorage_bucket "replays content"
        objstorage_rpc -> winery "get, upserts or deletes objects"
        objstorage_rpc -> path_slicing "get, upserts or deletes objects"

        // provenance
        scanner -> webapp "Sends authenticated requests" "rpc" "provenance" {
            properties {
              role "XXXXX"
            }
        }

        webapp -> provenance_rpc "Sends requests" "rpc" "provenance,,overlapped"
        provenance_rpc -> graph_grpc "Sends requests" "grpc" "provenance,overlapped"

        webapp -> provenance_grpc "Sends requests" "grpc" "provenance,,overlapped"
        provenance_grpc -> provenance_parquet_files "Queries files" "grpc" "provenance,overlapped"

        // alter/takedown
        codeOwner -> dpo "requests a takedown or a name change" "" "tdn"
        dpo -> systemAdministrator "notifies of a takedown to proceed" "" "tdn"
        dpo -> webapp "adds an entry in the mailmap" "" "tdn"
        webapp -> masking_proxy_db "Refreshes masking and mailmap information"

        systemAdministrator -> swh "proceeds a take down request""" "tdn"
        systemAdministrator -> alter_cli "launchs a takedown of an origin" "cli" "tdn"
        systemAdministrator -> blocking_proxy_cli "Manages blocked objects" "cli" "tdn"
        systemAdministrator -> masking_proxy_cli "Manages masked objects" "cli" "tdn"
        masking_proxy_cli -> masking_proxy_db "Manages masked objects" "python" "sql"

        alter_cli -> graph_rpc "gets the objects related to an origin" "rpc" "tdn"
        alter_cli -> storage_rpc "gets the recent objects related to an origin \n removes objects \n restores objects" "rpc" "tdn"
        alter_cli -> alter_recovery_bundle "saves to" "" "tdn"
        alter_cli -> alter_recovery_bundle "restores from" "" "tdn"
        alter_cli -> kafka "removes objects" "tcp""tdn"
        alter_cli -> objstorage_rpc "removes contents" "rpc" "tdn"
        alter_cli -> search_rpc "removes origins" "rpc" "tdn,search"

        swh -> forge "gets repository list and contents"

        loader -> forge "gets a repository"
        lister -> forge "gets available repositories"

        webapp -> keycloak "gets authenticated user roles" "" "provenance,overlapped"

        staging = deploymentEnvironment "Staging" {
          pg = deploymentGroup "Postgresql"
          cassandra = DeploymentGroup "Cassandra"

          rp0 = deploymentNode "rp0" {

              stg_hitch = infrastructureNode "hitch" {
                description "ssl termination"
              }
              stg_varnish = infrastructureNode "varnish" {
                description "cache and reverse-proxy"
              }
              stg_hitch -> stg_varnish ""
          }

          deploymentNode "kafkaX" {
            instances 1
            containerInstance "kafka" "pg,cassandra" {
            }
          }

          deploymentNode "search-esnodeX" {
            instances 1
            containerInstance "elasticsearch" "pg,cassandra" {
            }
          }

          deploymentNode "kelvingrove" {
            dep_stg_keycloak = containerInstance "keycloak" "cassandra,pg" "provenance"
          }

          archive_staging_rke2 = deploymentNode "archive-staging-rke2" {
            tags ""

            deploymentNode "ingress-controler" {
              tags "Kubernetes - svc"
              nginx_stg = infrastructureNode "nginx" "cassandra" {
                tags "Kubernetes - deploy"
              }
            }

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
                  tags provenance_v2,provenance
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

              storage_rpc_stg = containerInstance "storage_rpc" "cassandra" {
                  tags "Kubernetes - deploy"
              }
              deploymentNode "provenance-ingress" {
                tags "Kubernetes - ing"
                url "http://provenance-local"

                containerInstance "provenance_grpc" "cassandra,pg" {
                  tags "Kubernetes - deploy"
                }
              }

              coarnotify_stg_ingress = deploymentNode "coarnotify-ingress" "cassandra" {
                tags "Kubernetes - ing"
                url "http://coar-inbox.internal.staging.swh.network"

                containerInstance "coarnotify_rpc" "cassandra" {
                  tags "Kubernetes - deploy"
                }
              }

              deploymentNode "pgcluster" {
                tags "Kubernetes - svc"

                containerInstance "coarnotify_db" "cassandra" {
                  tags db
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
              deploymentNode "search-rpc-ingress" {
                tags "Kubernetes - ing"

                containerInstance "search_rpc" "cassandra,pg" {
                  tags "Kubernetes - deploy"
                }
              }

              containerInstance "search_journal_client" "cassandra" {
                tags "Kubernetes - deploy"
                description "objects"
              }
              containerInstance "search_journal_client" "cassandra" {
                tags "Kubernetes - deploy"
                description "indexed"
              }

              containerInstance "webapp" "cassandra" {
                tags "Kubernetes - deploy"

                description "webhook webapp"
              }
              containerInstance "objstorage_rpc" "cassandra-rw" {
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

          stg_varnish -> nginx_stg ""
          nginx_stg -> coarnotify_stg_ingress
        }

        production = deploymentEnvironment "Production" {
          moma = deploymentNode "moma" {
              prd_hitch = infrastructureNode "hitch" {
                description "ssl termination"
                tags objstorage_ro
              }
              prd_varnish = infrastructureNode "varnish" {
                description "cache and reverse-proxy"
                tags objstorage_ro
              }
              prd_hitch -> prd_varnish ""
          }

          deploymentNode "kelvingrove" {
            containerInstance "keycloak" "cassandra,pg" "provenance,provenance_v2"
          }

          deploymentNode "search-esnodeX" {
            instances 3
            containerInstance "elasticsearch" "pg,cassandra" {
            }
          }

          deploymentNode "rancher-node-highmem0[1-2]" {
            containerInstance "graph_grpc" "cassandra,pg" "provenance_v2"
          }

          deploymentNode "kafkaX" {
            instances 4
            containerInstance "kafka" "cassandra,pg"
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

              deploymentNode "provenance-ingress" {
                tags "Kubernetes - ing"
                url "http://provenance-local"
                description "http://provenance-local"

                containerInstance "provenance_rpc" "cassandra,pg"
              }
            }

            deploymentNode "swh-cassandra" {
              tags "Kubernetes - ns"

              deploymentNode "search-rpc-ingress" {
                tags "Kubernetes - ing"

                containerInstance "search_rpc" "cassandra,pg" {
                  tags "Kubernetes - deploy"
                }
              }

              containerInstance "search_journal_client" "cassandra" {
                tags "Kubernetes - deploy"
                description "objects"
              }
              containerInstance "search_journal_client" "cassandra" {
                tags "Kubernetes - deploy"
                description "indexed"
              }

              deploymentNode "storage_ingress" {
                tags "Kubernetes - ing"

                containerInstance "storage_rpc" "cassandra" {
                  description "ro-storage"
                }
                storage_rpc_prd = containerInstance "storage_rpc" "cassandra" {
                  description "rw-storage"
                }
              }

              deploymentNode "webapp_ingress" {
                tags "Kubernetes - ing"

                containerInstance "webapp" "cassandra" {
                  description "archive webapp"
                }
              }

              production_objstorage_ro_ingress = deploymentNode "objstorage_ro_ingress" {
                tags "Kubernetes - ing"
                url "https://objstorage.softwareheritage.org"
                description "https://objstorage.softwareheritage.org"

                containerInstance "objstorage_rpc" "cassandra" {
                  tags "objstorage_ro"
                  description "Objstorage read-only"
                }
              }
               production_swh_secrets = infrastructureNode "secrets" {
                 tags "Kubernetes - secret, objstorage_ro"
               }

              production_objstorage_ro_ingress -> production_swh_secrets "ingress-objstorage-ro-auth-secrets"

              coarnotify_prd_ingress = deploymentNode "coarnotify-ingress" "cassandra" {
                tags "Kubernetes - ing"
                url "http://coar-inbox.internal.softwareheritage.org"

                containerInstance "coarnotify_rpc" "cassandra" {
                  tags "Kubernetes - deploy"
                }
              }

              deploymentNode "pgcluster" {
                tags "Kubernetes - svc"

                containerInstance "coarnotify_db" "cassandra" {
                  tags db
                }
              }
            }


            deploymentNode "ingress-controler" {
              tags "Kubernetes - svc"

              nginx_prd = infrastructureNode "ingress-nginx" {
                tags "Kubernetes - deploy, objstorage_ro"
              }
            }
            nginx_prd -> production_objstorage_ro_ingress "https://objstorage.softwareheritage.org"
            nginx_prd -> coarnotify_prd_ingress

            prd_varnish -> nginx_prd
          }

      }


      cea = deploymentEnvironment "cea_winery" {
          bastion = deploymentNode "angrenost" {
              CEA_VPN = infrastructureNode "VPN" {
                description "ssl termination"
              }
          }
          gloin001 = deploymentNode "gloin001" {
              gloin001_haproxy = infrastructureNode "HaProxy" {
                description "LoadBalancer"
              }
              gloin001_patroni = infrastructureNode "Patroni" {
                description "HA PG"
              }
              gloin001_postgresql = infrastructureNode "PostgreSQL" {
                description "Winery database"
                tag db
              }
              gloin001_winery_reader = containerInstance winery_rpc {
                description "Read-only instance"
              }
              gloin001_winery_writer = containerInstance winery_rpc {
                description "Read-write instance"
              }
              gloin001_winery_cleaner = infrastructureNode "Winery shard cleaner" { }
              gloin001_winery_packer = infrastructureNode "Winery shard packer" { }
              gloin001_winery_rdb = infrastructureNode "Winery rbd mounter" {}
          }
          gloin002 = deploymentNode "gloin002" {
              gloin002_haproxy = infrastructureNode "HaProxy" {
                description "LoadBalancer"
              }
              gloin002_patroni = infrastructureNode "Patroni" {
                description "HA PG"
              }
              gloin002_postgresql = infrastructureNode "PostgreSQL" {
                description "Winery database"
                tag db
              }
              gloin002_winery_reader = infrastructureNode "Winery Reader" { }
              gloin002_winery_writer = infrastructureNode "Winery Writer" { }
              gloin002_winery_rdb = infrastructureNode "Winery rbd mounter" {}
          }
          cea_ceph = deploymentNode "ceph" {
            ceph_cluster = infrastructureNode "Ceph cluster"
          }

          CEA_VPN -> gloin001_haproxy "" "http"
          CEA_VPN -> gloin002_haproxy ""
          gloin001_patroni -> gloin002_patroni "Primary - Secondary management" "" ""
          gloin002_patroni -> gloin001_patroni "Primary - Secondary PG management" "" ""
          gloin001_patroni -> gloin001_postgresql "checks"
          gloin002_patroni -> gloin002_postgresql "checks"
          gloin001_postgresql -> gloin002_postgresql "Replicates"
          gloin002_postgresql -> gloin001_postgresql "Replicates"
          gloin001_haproxy -> gloin001_winery_reader "Reads contents" "http"
          gloin001_haproxy -> gloin002_winery_reader "Reads contents (backup)" "http" "backup,overlapped"
          gloin002_haproxy -> gloin002_winery_writer "Reads/Writes contents" "http" "overlapped"
          gloin002_haproxy -> gloin001_winery_writer "Reads/Writes contents (backup)" "http" "backup,overlapped"

          gloin001_winery_reader -> gloin001_postgresql "Gets shards info / contents"
          gloin002_winery_writer -> gloin002_postgresql "Writes contents"

          gloin001_winery_cleaner -> gloin002_postgresql "Cleans packed shards" "" "overlapped"

          gloin001_winery_packer -> gloin001_postgresql "Reads shard content"
          gloin001_winery_packer -> gloin001_winery_packer "Locally builds winery shards"
          gloin001_winery_packer -> cea_ceph "Writes rbd image" "" "overlapped"

          gloin001_winery_rdb -> gloin001_postgresql "Gets shards ready list"
          gloin001_winery_rdb -> cea_ceph "Mounts rbd image"
          gloin001 -> cea_ceph "Reads rbd image content"

          gloin002_winery_rdb -> gloin002_postgresql "Gets shards ready list"
          gloin002_winery_rdb -> cea_ceph "Mounts rbd image"
          gloin002 -> cea_ceph "Reads rbd image content"
      }
    }



####################################################################################################
    views {

      theme "https://static.structurizr.com/themes/kubernetes-v0.3/theme.json"

      deployment * cea_winery "CEA_Winery_" {
        title "CEA - winery deployment"
        include *
        autolayout
      }

      deployment * staging "staging_provenance" {
          title "swh-provenance Staging deployment"
          include "element.tag==provenance"

          autolayout
      }

      deployment * production "production_provenance" {
          include "element.tag==provenance_v2"

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

      deployment * production "production_objstorage_ro" {
          include "element.tag==objstorage_ro"
          autolayout lr
      }

      systemContext swh "global_view" {
          include *
          autolayout
      }

      container swh "global" {
        include *
        autolayout
      }

      container swh "provenance_pre_v3_infra" {
        title "Provenance pre-v0.3 Infrastructure"
        include provenance_rpc
        include graph_grpc
        autoLayout
      }

      container swh "provenance_v3_infra" {
        title "Provenance v0.3 Infrastructure"
        include provenance_grpc
        include provenance_parquet_files

        autoLayout
      }

      container swh "coarnotify_infra" {
        title "Coar Notify infrastructure"
        include coarnotify_rpc
        include coarnotify_db
        include storage_rpc
        include storage_db

        include fairCorePartners
        autoLayout
      }
      deployment * staging "staging_coarnotify_deployment" {
          title "COAR notify Staging deployment"
          include storage_rpc_stg
          include coarnotify_rpc
          include coarnotify_db
          include coarnotify_stg_ingress
          include nginx_stg
          include rp0
          autolayout
      }

      deployment * production "production_coarnotify_deployment" {
          title "COAR notify Production deployment"
          include storage_rpc_prd
          include coarnotify_rpc
          include coarnotify_db
          include coarnotify_prd_ingress
          include storage_rpc_prd
          include nginx_prd
          include moma
          autolayout
      }


      container swh "storage" {
        include "->storage_rpc->"
        autoLayout
      }

      container swh "citation" {
        include "element.tag==citation"
        exclude "relationship.tag!=citation"
        autoLayout
      }

      component storage_rpc "storage_components" {
        include *
        autoLayout
      }

      container swh "scheduler" {
        include "->scheduler->"
        autoLayout
      }

      container swh "search" {
        include "element.tag==search"
        // include "->search_rpc->"
        // exclude "relationship.tag!=search"
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

      container swh "winery" {
        include "winery_db"
        include "winery_shard_packer"
        include "winery_shard_cleaner"
        include "winery_rpc"
        include "winery_rbd"
        include "winery_os"
        include "ceph"
        include "storage_rpc"
        include "objstorage_replayer"
        autolayout lr
      }

      dynamic swh "winery-shards-writing" {
        title "Winery shard preparation steps"

        winery_rpc -> winery_db "Creates a new shard (status WRITING)"
        winery_rpc -> winery_db "Adds contents to the shard"
        winery_rpc -> winery_db "Adds id -> shard reference"
        winery_rpc -> winery_db "Updates shard status to FULL"

        autolayout lr
      }

      dynamic swh "winery-shards-packing" {
        title "Winery shard preparation steps"

        winery_shard_packer -> winery_db "updates FULL shards to PACKING"
        winery_shard_packer -> winery_db "Read shard contents"
        winery_shard_packer -> ceph "Save the shard into the rbd image"
        winery_shard_packer -> winery_db "Updates shard status to PACKED"

        autolayout  lr
      }

      dynamic swh "winery-shards-mounting" {
        title "Winery shard preparation steps"

        winery_rbd -> winery_db "Waits for PACKED shards"
        winery_rbd -> winery_os "Mounts the rbd image"
        winery_rbd -> winery_db "Updates the shard mount status"

        autolayout  lr
      }

      dynamic swh "winery-shards-cleaning" {
        title "Winery shard preparation steps"

        winery_shard_cleaner -> winery_db "Waits for a PACKED and mounted shard"
        winery_shard_cleaner -> winery_db "Updates status to CLEANING"
        winery_shard_cleaner -> winery_db "Removes shard content"
        winery_shard_cleaner -> winery_db "Update status to READONLY"

        autolayout  lr
      }

      dynamic swh "add-forge-now" {
        title "Add forge now interactions"
        systemAdministrator -> webapp "accepts a add forge now request"
        webapp -> gitlab "Triggers a pipeline"
        gitlab -> scheduler "Registers a lister"
        gitlab -> scheduler "Checks the listed origins"
        gitlab -> scheduler "Schedules the first visits"
        gitlab -> scheduler "Checks the visited origins"
        gitlab -> webapp "Updates request status if ok"
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
        element "system" {
          shape RoundedBox
          background lightblue
        }

        relationship overlapped {
          position 75
        }
        relationship "Relationship" {
          dashed false
        }
        relationship backup {
          dashed true
        }

      }

    }


}
