workspace "Code Commons" "Description" {

    model {
        github = softwareSystem "Github"

        hpc = softwareSystem "HPC" {
            !adrs "doc/adr/hpc"

            frontend = container "Frontend Nodes" {
                cloner = component "cloner" "git" {
                  !adrs "doc/adr/hpc/cloner"

                  tags job
                }
                ssh_server = component "ssh" {
                    tags service

                }
            }
            compute = container "Compute Nodes" {
                kafka = component "kafka" {
                  tags service
                }
                loader = component "repository loader" "" "python" {
                  !adrs "doc/adr/loader"
                  tags job
                }

                deduplicator = component "deduplicator" "" "python" {
                  tags job
                }
                compute_index = component "index" "" "TBD" {
                  !adrs "doc/adr/hpc/index"
                  tags service
                }
            }
            hpc_storage = container "Storage" {
                tags file
                repo_list = component "Repository list" {
                    tags file
                    technology "CSV"
                }
                repo_clone = component "Repository clones" {
                    tags file
                    technology "Git clone"
                }

                kafka_logs = component "undeduplicated objects" {
                    tags file
                    technology "Kafka logs"
                }

                repo_status = component "Repository status" {
                    tags file
                    technology "TBD"
                }

                object_index = component "SWHid index" {
                  tags file
                  technology "TBD"
                }
            }
        }

        swh = softwareSystem "Software Heritage" {
            repo_extractor = container "Repository extractor" {
                tags new
                technology python
                !adrs "doc/adr/repository_extractor"
                description "Generate the list of unvisited github origins to process on the HPC"
            }
            swh_scheduler = container "swh-scheduler" {
                tags notimpacted
                technology "RPC"
                description "not impacted"
            }
            dataset_importer = container "dataset importer" {
                tags new
                technology "python"
                !adrs "doc/adr/dataset_importer"
                description "Import a SWH dataset into the SWH main archive"
            }
            data_syncer = container "data syncer" {
                tags new
                technology bash
                !adrs "doc/adr/data_syncer"
                description "Synchronize the HPC project storage with the SWH Storage"
            }
            swh_mass_storage = container "storage" {
                tags file new

                swh_repo_list = component "swh_repo_list" {
                    tags file
                }
            }
            swh_storage = container "swh-storage" {
                tags notimpacted
                description "not impacted"
            }
        }

        swh -> hpc "sends a repository list and downloads deduplicated repository contents"
        swh -> ssh_server "sends a repository list" "scp"
        swh -> ssh_server "sends the known objects index"
        swh -> frontend "downloads computed datasets" "rsync"
        repo_extractor -> swh_scheduler "extracts unvisited origins" "sql" "overlapped"
        repo_extractor -> swh_storage "reserves origin visit" "rpc"
        repo_extractor -> swh_repo_list "saves repo list" "" "overlapped"
        dataset_importer -> swh_mass_storage "reads a dataset"
        dataset_importer -> swh_storage "adds content" "" "overlapped"
        dataset_importer -> swh_scheduler "creates a recurrent visit" "rpc" "overlapped"
        data_syncer -> swh_mass_storage "synchronizes content and delete imported datasets"
        data_syncer -> dataset_importer "launchs the dataset import" "TBD"

        // Frontends
        cloner -> github "clones repositories" "git"
        cloner -> hpc_storage "reads repository list and stores repository contents"
        cloner -> repo_list "reads repo list"
        cloner -> repo_clone "writes repo content"
        cloner -> repo_status "adds repositories status info"

        // Compute
        compute -> hpc_storage "reads repositories and writes computed data"
        loader -> kafka "writes repository content" "" "overlapped"
        deduplicator -> kafka "read raw data"
        deduplicator -> compute_index "checks object existence and update index"
        compute_index -> hpc_storage "reads and writes index data"
        loader -> repo_status "updates the status of a repository"
        deduplicator -> repo_status "updates repository status"
        deduplicator -> hpc_storage "writes swh and anonymized datasets" "" "overlapped"

        // HPC Storage
        compute_index -> object_index "reads and writes"
        loader -> repo_clone "reads a repository content"
        data_syncer -> hpc_storage "synchronizes content and delete imported datasets"
        frontend -> hpc_storage "stores repositoriy list and clones, reads datasets"
        ssh_server -> repo_list "stores repositories list"
        // TODO: Change this, the ssh / frontend can't access the compute services directly
        ssh_server -> compute_index "stores known objects index"
        kafka -> kafka_logs "reads and write log files"

    }

    views {
        systemContext swh {
            include *
            autolayout
        }

        container swh "swh_macro" {
            include *
            autolayout
        }

        systemContext hpc {
            include *
            autolayout
        }

        container hpc "hpc_macro" {
            include *
            autolayout
        }

        component frontend "frontend-components" {
            include "*"
            autolayout
        }

        component compute "compute-components" {
            include "*"
            autolayout
        }

        component hpc_storage "Storage" {
            include *
            autolayout
        }

        dynamic frontend {
            title "Step 0.1 - Provide the repository list"
            swh -> ssh_server "sends the repository list"
            ssh_server -> repo_list "stores repository list"
            autolayout lr
        }

        dynamic frontend {
            title "Step 0.2 - Provide the known objects index"
            swh -> ssh_server "sends the known objects index"
            ssh_server -> compute_index "stores known objects index"
            autolayout lr
        }

        dynamic frontend {
            title "Step 1 - Repository cloning process"
            cloner -> repo_list "retrieves repository list"
            cloner -> github "clones repository [iterative]"
            cloner -> repo_clone "writes repository content [iterative]"
            cloner -> repo_status "adds repository (status: CLONED)"
            autolayout
        }

        dynamic compute {
            title "Step 2.1 - Repository data processing"
            loader -> repo_clone "Reads CLONED repository content"
            loader -> kafka "writes repository content"
            loader -> repo_status "updates repository status (LOADED)"
            autolayout
        }

        dynamic compute {
            title "Step 2.2 - Data deduplication"
            deduplicator -> kafka "read LOADED repository data"
            deduplicator -> compute_index "checks duplicate objects and writes unreferenced objects"
            deduplicator -> repo_status "updates repository status (DEDUPLICATED)"
            autolayout
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
            element "external" {
                background darkseagreen
            }
            element "file" {
                shape Folder
                background lightgreen
            }

            element "new" {
                background lightblue
                border dotted
            }
            element "notimpacted" {
                background orange
                border dotted
            }
            element "job" {
              background lightblue
              shape Ellipse
            }
            element "service" {
              background orange
              shape RoundedBox
            }
            relationship overlapped {
              position 75
            }
        }

    }


    configuration {
        # scope softwaresystem
        # scope unscoped
    }

}