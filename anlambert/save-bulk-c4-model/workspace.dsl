workspace {

  model {

    save_bulk_user = person "Save bulk user" {
      tags "node" "user"
    }

    swh = softwareSystem "Software Heritage" {

      webapp = group "swh-web" {

        web_api = container "Web API endpoint" {
          description "Performs basic checks on submitted origins"
          tags "node" "web_api"
        }

        listing_endpoint = container "HTTP endpoint" {
          description "List origins submitted through a save bulk request"
          tags "node"
        }

        web_database = container "Webapp database" {
          tags "node" "database"
          web_api -> this "Writes submitted origins if all checks passed"
          listing_endpoint -> this "Reads origins associated to a request"
        }

      }

      scheduler = group "swh-scheduler" {

        scheduler_runner = container "Scheduler runner service" {
          description "Schedules lister tasks inserted into database"
          tags "node" "scheduler_runner"
        }

        scheduler_api = container "Scheduler RPC API" {
          tags "node"
          scheduler_runner -> this "Fetch tasks to schedule"
        }

        scheduler_database = container "Scheduler database" {
          tags "node" "database"
          scheduler_api -> this "Writes or reads listed origins and tasks"
        }

        scheduler_save_bulk_scheduling = container "Save bulk origins scheduling service" {
          description "Schedules loading tasks for save bulk origins using dedicated RabbitMQ queues"
          tags "node" "scheduler_save_bulk_scheduling"
        }

      }

      listers = group "swh-lister" {

        save_bulk_lister = container "Save bulk lister" {
          description "Performs advanced checks on submitted origins: check URLs can be found and check visit types are valid"
          tags "node" "save_bulk_lister"
        }

      }

      loaders = group "swh-loader-*" {

        swh_loaders = container "SWH loaders" {
          description "Load origins with various visit types: bzr, cvs, hg, git, svn and tarball-directory"
          tags "node" "swh_loaders"
        }

      }

    }

    save_bulk_user -> web_api "Submits origins through authenticated POST request to Web API"
    web_api -> scheduler_api "Creates a save bulk lister task to schedule if all checks passed" {
      tags "lister_task_creation"
    }
    scheduler_runner -> save_bulk_lister "Send save bulk lister task created by the webapp to celery"
    save_bulk_lister -> listing_endpoint "Reads origins submitted through a save bulk request"
    save_bulk_lister -> scheduler_api "Record listed origins that are valid"
    scheduler_save_bulk_scheduling -> swh_loaders "Sends loading tasks to celery"
    scheduler_save_bulk_scheduling -> scheduler_api "Reads origins recorded by save bulk lister"
  }

  views {

    container swh {
      include *
      autolayout
    }

    styles {
      element "node" {
        metadata false
      }
      element "user" {
        shape Person
      }
      element "database" {
        shape Cylinder
      }
      element "web_api" {
        icon number-one.png
      }
      element "scheduler_runner" {
        icon number-two.png
      }
      element "save_bulk_lister" {
        icon number-three.png
      }
      element "scheduler_save_bulk_scheduling" {
        icon number-four.png
      }
      element "swh_loaders" {
        icon number-five.png
      }
      relationship "lister_task_creation" {
        position 15
      }
    }

  }

}