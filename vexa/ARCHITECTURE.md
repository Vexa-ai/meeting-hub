# Vexa Service Layer: Architecture Overview

This document outlines the architecture of the Vexa Service Layer, which operates as a "Retailer" on top of the core Vexa infrastructure API (the "Wholesaler").

## The Wholesaler/Retailer Model

The key concept is the separation of the user-facing service from the low-level infrastructure management.

### Vexa Infra (The Wholesaler)

This is the complete, underlying Vexa application. It includes the full infrastructure stack:

*   **`bot-manager`**: Manages the lifecycle of bot Docker containers.
*   **`WhisperLive`**: Handles real-time audio transcription.
*   **`transcription-collector`**: Gathers and stores transcription data.
*   **`admin-api`**: Manages system-level users and API tokens.
*   **Datastores**: PostgreSQL and Redis.

The Wholesaler exposes its powerful capabilities through a secure API Gateway.

### Vexa Service (The Retailer)

This application, the Vexa Service Layer, is a repurposed version of the original Vexa codebase. Its primary role is to serve end-users, acting as a value-added reseller of the Wholesaler's services.

All the low-level infrastructure components (`bot-manager`'s Docker integration, `WhisperLive`, etc.) have been "hollowed out" and replaced with API calls to the Wholesaler.

## Core Principles

1.  **Maximal Code Reuse**: The Retailer is a fork of the Wholesaler's codebase, preserving the application logic, data models, and API structure.
2.  **Infrastructure Abstraction**: The Retailer does not manage any transcription or bot infrastructure directly. It is purely a consumer of the Wholesaler's API.
3.  **Unified System Identity**: The Retailer authenticates to the Wholesaler API using a single, system-level API key. From the Wholesaler's perspective, all actions are performed by this one "system user."
4.  **Independent User Management**: The Retailer is responsible for managing its own end-users. It maintains its own user database and authentication system, completely separate from the Wholesaler's user management.

## Request and Data Flow

The flow is designed to abstract the underlying complexity from the end-user.

1.  **User Request**: An end-user sends a request (e.g., to start a bot) to the Retailer's API gateway, using an API key provided by the Retailer.
2.  **Retailer Authentication**: The Retailer authenticates its own user.
3.  **Proxy to Wholesaler**: The relevant service within the Retailer (e.g., its `bot-manager`) constructs a corresponding request to the Wholesaler's API gateway. This request is authenticated using the Retailer's master system API key.
4.  **Wholesaler Execution**: The Wholesaler receives the request, validates the Retailer's system token, and executes the low-level action (e.g., spinning up a Docker container for the bot).
5.  **Data Mapping**: The Retailer receives the response from the Wholesaler (e.g., a new `meeting_id`). It then stores a mapping between its own end-user and this `meeting_id` in its own database. This mapping is crucial for data segregation and ensuring that end-users can only access their own meetings and transcripts.

## Key Code Modifications

The transition from Wholesaler to Retailer involves modifying these key areas:

*   **`services/bot-manager/`**: The logic for interacting with the Docker daemon (`docker_utils.py`) is replaced with an HTTP client that calls the Wholesaler's `/bots` endpoints.
*   **`services/api-gateway/`**: Routes that retrieve data (e.g., `/transcripts/{...}`) are rewired to fetch data from the Wholesaler's API instead of from a local database via the `transcription-collector`.
*   **`docker-compose.yml`**: The composition is simplified significantly, removing services like `whisperlive` and `transcription-collector`, as they are now managed by the Wholesaler. New environment variables are added to configure the connection to the Wholesaler API (`VEXA_INFRA_API_URL`, `VEXA_INFRA_API_KEY`).

This architecture allows us to rapidly build and deploy a multi-tenant, user-facing service without duplicating the complex backend infrastructure, leveraging the robust and scalable foundation provided by the Vexa Wholesaler API. 