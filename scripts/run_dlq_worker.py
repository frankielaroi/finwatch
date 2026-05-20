import sys

from app.tasks.worker_entrypoint import main

if __name__ == "__main__":
    main(["dlq", *sys.argv[1:]])
