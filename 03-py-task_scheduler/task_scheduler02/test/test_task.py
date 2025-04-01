import requests
import json

# URL where the Flask app is running (change the port if needed)
url = "http://localhost:5000/tasks"

# Example data that matches the expected schema of your Flask app
data = {
    "task_type": "shell",
    "task_name": "Example Task",
    "description": "This is an example shell task.",
    "task_id": "task001",
    "execution_params": {
        "script": "echo Hello, world!"
    },
    "scheduling_rule": {
        "type": "interval",
        "interval": {"seconds": 3600}  # Run every hour
    },
    "priority": 1,
    "dependencies": []
}

# Convert data to JSON
json_data = json.dumps(data)

# Set appropriate headers for JSON
headers = {
    'Content-Type': 'application/json'
}

# Optionally, include an authorization token if needed
# headers['Authorization'] = 'Bearer your_token_here'

# Send the POST request
response = requests.post(url, headers=headers, data=json_data)

# Print response from the server
print("Status Code:", response.status_code)
print("Response Body:", response.text)
print("Response Body:", response.json())
