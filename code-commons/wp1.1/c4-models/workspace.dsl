workspace "Code Commons" "Description" {

    model {
        github = softwareSystem "Github"

        hpc = softwareSystem "HPC" {
            frontend = container "Frontend Nodes" {
                cloner = component "cloner" "git" {
                  tags job
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
                index = component "index" "" "TBD" {
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
        swh -> frontend "sends a repository list" "scp"
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

        // Compute
        compute -> hpc_storage "reads repositories and writes computed data"
        loader -> kafka "writes repository content" "" "overlapped"
        deduplicator -> kafka "read raw data"
        deduplicator -> index "checks object existence and update index"
        index -> hpc_storage "reads and writes index data"
        deduplicator -> hpc_storage "writes swh and anonymized datasets" "" "overlapped"

        // HPC Storage
        index -> object_index "reads and writes"
        loader -> repo_clone "reads a repository content"
        data_syncer -> hpc_storage "synchronizes content and delete imported datasets"
        frontend -> hpc_storage "stores repositoriy list and clones, reads datasets"
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
