# Chat Conversation Engine API

## Introduction
The Chat Conversation Engine API is a robust backend service designed to handle chat operations, authentication, and configuration management for chatbots and other conversational interfaces. It leverages FastAPI to provide a high performance, easy to integrate solution for managing chat configurations and processing chat completions with support for custom plugins and tools.

## Features
- **Authentication System:** Secure endpoints using JWT authentication.
- **Dynamic Configuration:** Fetch and update conversation configurations dynamically.
- **Conversation Memory Management:** Store and retrieve conversation states to maintain context in ongoing interactions.
- **Completions API:** Process chat messages using configured conversation agents.

## Prerequisites
Before you can run the server, you need:
- Python 3.11.4 or higher
- MongoDB running on the default port
- Environment variables for DB

## Installation

Clone the repository and navigate into the project directory:

```bash
git clone https://github.com/samar-kapture/KapKB
cd KapKB
```

### Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Running the Server

Start the server using:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API Endpoints

- `POST` `/kapnotes/auth/login`: Authenticate users and return JWT.
- `POST` `/kapnotes/auth/validate`: Validate the authentication token.
- `POST` `/kapnotes/config/get`: Fetch a specific configuration for a client.
- `POST` `/kapnotes/config/add`: Add or update a conversation configuration.
- `POST` `/kapnotes/config/delete`: Delete a conversation configuration.
- `POST` `/kapnotes/chat/completions`: Process and respond to chat completions based on the configuration.

## Contact

Samar K - @samar-kapture - samar.k@kapturecrm.com
