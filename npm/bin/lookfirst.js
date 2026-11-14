#!/usr/bin/env node
// This npm package only points to lookfirst, which is a Python tool. It has no install
// scripts and no dependencies, and running it only prints how to install the real one.
"use strict";

process.stderr.write(
  [
    "lookfirst isn't distributed through npm. This package only points to it.",
    "",
    "Install it with uv (https://docs.astral.sh/uv/):",
    "  uv tool install lookfirst",
    "",
    "Official sources: https://github.com/lookfirst-dev/lookfirst and the lookfirst package on PyPI.",
    "",
  ].join("\n"),
);
process.exitCode = 1;
