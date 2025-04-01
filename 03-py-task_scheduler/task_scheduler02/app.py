import os
import json
import threading
import requests
import logging
from datetime import timedelta
from flask import Flask, request, jsonify, render_template
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from resource_monitor import monitor_resources
from db_config import mysql_conn, mysql_cursor, redis_client

# Flask app initialization
app = Flask(__name__)
# Secret key for JWT token encryption
app.config['JWT_SECRET_KEY'] = 'super-secret-key'
# Token expiration after 1 hour
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)  # JWT manager setup


# Scheduler to manage task execution
scheduler = BackgroundScheduler()


# Task concurrency control
MAX_CONCURRENT_TASKS = 5
concurrent_tasks = 0
concurrent_lock = threading.Lock()

# Logging configuration
logging.basicConfig(
    filename='task_scheduler.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ==========================
#       AUTHENTICATION
# ==========================

@app.route('/login', methods=['POST'])
def login():
    """
    Handle user login and return a JWT token.
    Returns:
        JSON response with access token or error message.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Simple username and password check (hardcoded for demonstration)
    if username == 'admin' and password == 'password':
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200

    return jsonify({"msg": "Invalid username or password"}), 401


# ==========================
#      TASK MANAGEMENT
# ==========================

@app.route('/tasks', methods=['POST'])
# @jwt_required()
def create_task():
    """
    Create a new task with the given parameters.

    - Validates input parameters
    - Stores task in MySQL and Redis
    - Adds task to the scheduler with appropriate trigger

    Returns:
        JSON success or failure message.
    """
    data = request.get_json()
    task_type = data.get('task_type')
    task_name = data.get('task_name')
    description = data.get('description')
    task_id = data.get('task_id')
    execution_params = data.get('execution_params')
    scheduling_rule = data.get('scheduling_rule')
    priority = data.get('priority')
    dependencies = data.get('dependencies', [])

    # Validate required fields
    if not all([task_type, task_name, task_id, scheduling_rule]):
        return jsonify({"msg": "Missing required fields"}), 400

    # Check for circular dependencies
    if check_circular_dependency(task_id, dependencies):
        return jsonify({"msg": "Circular dependency detected"}), 400

    # Insert task into MySQL
    sql = """
        INSERT INTO tasks (task_id, task_name, description, task_type, execution_params, scheduling_rule, priority, dependencies)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """  # SQL: Add task details to the tasks table
    val = (
        task_id, task_name, description, task_type,
        json.dumps(execution_params),
        json.dumps(scheduling_rule),
        priority, json.dumps(dependencies)
    )
    mysql_cursor.execute(sql, val)
    mysql_conn.commit()

    # Cache task in Redis
    redis_client.hset(task_id, mapping={
        "task_name": task_name,
        "description": description,
        "task_type": task_type,
        "execution_params": json.dumps(execution_params),
        "scheduling_rule": json.dumps(scheduling_rule),
        "priority": priority,
        "dependencies": json.dumps(dependencies),
        "status": "waiting"
    })

    # Schedule the task
    trigger = get_trigger(scheduling_rule)
    scheduler.add_job(execute_task, trigger=trigger, args=[task_id], id=task_id)

    return jsonify({"msg": "Task created successfully"}), 201


@app.route('/tasks', methods=['GET'])
# @jwt_required()
def get_tasks():
    """
    Retrieve all tasks with details.

    - Fetches task data from MySQL and Redis.
    - Returns a list of tasks.

    Returns:
        JSON list of tasks.
    """
    mysql_cursor.execute("SELECT * FROM tasks")  # SQL: Get all tasks from the tasks table
    tasks = mysql_cursor.fetchall()

    task_list = []
    for task in tasks:
        task_id = task[0]
        task_info = {
            "task_id": task_id,
            "task_name": task[1],
            "description": task[2],
            "task_type": task[3],
            "execution_params": json.loads(task[4]),
            "scheduling_rule": json.loads(task[5]),
            "priority": task[6],
            "dependencies": json.loads(task[7]),
            "status": redis_client.hget(task_id, "status").decode()
        }
        task_list.append(task_info)

    return jsonify(task_list), 200


@app.route('/tasks/<task_id>', methods=['DELETE'])
# @jwt_required()
def delete_task(task_id):
    """
    Delete an existing task by ID.

    - Removes task from scheduler, Redis, and MySQL.

    Args:
        task_id (str): Task identifier.

    Returns:
        JSON success or failure message.
    """
    # Remove task from scheduler
    scheduler.remove_job(task_id)

    # Delete task from MySQL
    sql = "DELETE FROM tasks WHERE task_id = %s"  # SQL: Remove task by task_id
    mysql_cursor.execute(sql, (task_id,))
    mysql_conn.commit()

    # Delete task from Redis
    redis_client.delete(task_id)

    return jsonify({"msg": "Task deleted successfully"}), 200


# ==========================
#      TASK EXECUTION
# ==========================

def execute_task(task_id, retry_count=0, max_retries=3):
    """
    Execute the given task and manage retries if it fails.

    Args:
        task_id (str): Task identifier.
        retry_count (int): Current retry attempt.
        max_retries (int): Maximum retry limit.

    Returns:
        None. Logs task results and updates status in Redis.
    """
    global concurrent_tasks
    with concurrent_lock:
        if concurrent_tasks >= MAX_CONCURRENT_TASKS:
            logging.info(f"Task {task_id} is waiting due to concurrent task limit.")
            return
        concurrent_tasks += 1

    task_info = redis_client.hgetall(task_id)
    task_info = {key.decode(): value.decode() for key, value in task_info.items()}
    task_type = task_info['task_type']
    execution_params = json.loads(task_info['execution_params'])
    dependencies = json.loads(task_info['dependencies'])

    # Check dependencies before executing
    for dep in dependencies:
        dep_status = redis_client.hget(dep, "status").decode()
        if dep_status != 'completed':
            logging.info(f"Task {task_id} is waiting for dependency {dep} to complete.")
            with concurrent_lock:
                concurrent_tasks -= 1
            return

    redis_client.hset(task_id, "status", "running")
    start_time = str(int(os.times()[4]))
    logging.info(f"Task {task_id} started at {start_time}")

    try:
        if task_type == 'shell':
            os.system(" ".join(execution_params))
        elif task_type == 'python':
            import subprocess
            subprocess.run(['python'] + execution_params, check=True)
        elif task_type == 'api':
            method = execution_params.get('method', 'GET')
            url = execution_params.get('url')
            headers = execution_params.get('headers', {})
            data = execution_params.get('data', {})
            if method.upper() == 'GET':
                requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                requests.post(url, headers=headers, data=data)

    except Exception as e:
        logging.error(f"Task {task_id} failed with error: {str(e)}")
        if retry_count < max_retries:
            logging.info(f"Retrying task {task_id} (attempt {retry_count + 1})")
            scheduler.add_job(
                execute_task,
                args=[task_id, retry_count + 1, max_retries],
                trigger=IntervalTrigger(seconds=5),
                id=f"{task_id}_retry_{retry_count + 1}"
            )
        else:
            redis_client.hset(task_id, "status", "failed")
            notify(task_id, "failed", str(e))
    else:
        end_time = str(int(os.times()[4]))
        logging.info(f"Task {task_id} completed at {end_time}")
        redis_client.hset(task_id, "status", "completed")
        notify(task_id, "completed", "")

    with concurrent_lock:
        concurrent_tasks -= 1


def get_trigger(scheduling_rule):
    """
    Generate a trigger for task scheduling based on the rule.

    Args:
        scheduling_rule (dict): Rule for task scheduling.

    Returns:
        Appropriate trigger object for apscheduler.
    """
    rule_type = scheduling_rule.get('type')
    if rule_type == 'fixed_time':
        return DateTrigger(run_date=scheduling_rule['run_date'])
    elif rule_type == 'interval':
        return IntervalTrigger(**scheduling_rule['interval'])
    elif rule_type == 'cron':
        return CronTrigger(**scheduling_rule['cron'])


def check_circular_dependency(task_id, dependencies):
    """
    Check for circular dependencies in task dependencies.

    Args:
        task_id (str): Task identifier.
        dependencies (list): List of task dependencies.

    Returns:
        bool: True if circular dependency found, otherwise False.
    """
    visited = set()
    stack = [task_id]

    while stack:
        current_task = stack.pop()
        if current_task in visited:
            return True
        visited.add(current_task)
        current_task_deps = json.loads(redis_client.hget(current_task, "dependencies").decode())
        stack.extend(current_task_deps)

    return False


def notify(task_id, status, error_info):
    """
    Notify the user about task completion or failure.

    Args:
        task_id (str): Task identifier.
        status (str): Task status (completed/failed).
        error_info (str): Error details (if any).

    Returns:
        None.
    """
    task_info = redis_client.hgetall(task_id)
    task_info = {key.decode(): value.decode() for key, value in task_info.items()}
    task_name = task_info['task_name']
    message = f"Task {task_name} ({task_id}) {status}"
    if status == 'failed':
        message += f" with error: {error_info}"
    logging.info(message)


# ==========================
#      HTML INTERFACES
# ==========================

@app.route('/ui', methods=['GET'])
def index_ui():
    """
    Render the main interface for the task scheduler.
    """
    return render_template('index.html')


@app.route('/ui/tasks', methods=['GET'])
# @jwt_required()
def tasks_ui():
    """
    Display all tasks in an HTML table.

    Returns:
        Rendered HTML template with task details.
    """
    mysql_cursor.execute("SELECT * FROM tasks")
    tasks = mysql_cursor.fetchall()
    task_list = []
    for task in tasks:
        task_id = task[0]
        task_info = {
            "task_id": task_id,
            "task_name": task[1],
            "description": task[2],
            "task_type": task[3],
            "execution_params": json.loads(task[4]),
            "scheduling_rule": json.loads(task[5]),
            "priority": task[6],
            "dependencies": json.loads(task[7]),
            "status": redis_client.hget(task_id, "status").decode()
        }
        task_list.append(task_info)
    return render_template('tasks.html', tasks=task_list)


@app.route('/ui/metrics', methods=['GET'])
# @jwt_required()
def metrics_ui():
    """
    Show system resource metrics from the database.

    Returns:
        Rendered HTML template with system metrics.
    """
    mysql_cursor.execute("SELECT created_at, cpu_usage, memory_usage FROM system_metrics ORDER BY created_at DESC LIMIT 10")
    metrics_data = mysql_cursor.fetchall()
    return render_template('metrics.html', metrics=metrics_data)


# ==========================
#    SCHEDULE MONITORING
# ==========================
# Schedule the resource monitor to run every 60 seconds
scheduler.add_job(
    monitor_resources,
    IntervalTrigger(seconds=60),
    id='resource_monitor',
    max_instances=1
)






# ==========================
#        MAIN ENTRY
# ==========================

if __name__ == '__main__':
    scheduler.start()
    app.run(debug=True)
