#!/bin/bash
# Go to the directory where the script is located
cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd
black --line-length 79 eot
black --line-length 79 examples
black --line-length 79 data_preparation