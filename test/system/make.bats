#!/usr/bin/env bats

load common

@test "Make simple PNB" {
    rm -rf simple_pnb
    prusaman make ${ROOT}/doc/examples/simple_pnb simple_pnb
}
