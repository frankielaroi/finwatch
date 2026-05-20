import sys

from app.tasks.worker_entrypoint import main

if __name__ == "__main__":
    main(["profile", *sys.argv[1:]])
