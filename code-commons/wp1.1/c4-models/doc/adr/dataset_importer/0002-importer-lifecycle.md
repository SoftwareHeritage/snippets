# 1. importer process lifecycle

Date: 2024-07-04

## Status

Proposal

## Context

In order to benefit of the kubernetes job management, we should design the dataset importer
to be runnable in a kubernetes job.

It implies the importer is called with a parameter to import a uniq dataset and exits with a
status matching the import result.
- 0 => OK
- != 0 => KO

Given the importent size of a dataset, it should not have any consequences on the kubernetes scheduler

## Decision

PENDING

## Consequences


