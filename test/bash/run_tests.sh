#!/usr/bin/env bash

# Run all Bats tests in the test/bash directory

find test/bash -name "*.bats" -exec bats {} \;