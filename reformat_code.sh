#!/bin/bash
# Go to the directory where the script is located
cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd
REQUIRED_VERSION="24.3.0"
black --required-version ${REQUIRED_VERSION} --line-length 79 eot
black --required-version ${REQUIRED_VERSION} --line-length 79 examples
black --required-version ${REQUIRED_VERSION} --line-length 79 data_preparation
