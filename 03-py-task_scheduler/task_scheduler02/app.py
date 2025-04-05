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
from db_config import redis_client  # Only Redis is imported here
from models import SessionLocal, TaskModel  # Use ORM for tasks

# Flask app initialization
app = Flask(__name__)

# Secret key for JWT token encryption
app.config['JWT_SECRET_KEY'] = 'super-secret-key'

# JWT token expiration time (1 hour)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

# Initialize JWT manager
jwt = JWTManager(app)

# Scheduler for task execution
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
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username == 'admin' and password == 'password':
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200

    return jsonify({"msg": "Invalid username or password"}), 401


# ==========================
#      TASK MANAGEMENT
# ==========================
@app.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    """
    Create a new task with the given parameters using ORM.

    - Validates input parameters
    - Stores task in the "tasks" table via ORM
    - Caches task in Redis
    - Adds task to the scheduler with an appropriate trigger
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

    if not all([task_type, task_name, task_id, scheduling_rule]):
        return jsonify({"msg": "Missing required fields"}), 400

    if check_circular_dependency(task_id, dependencies):
        return jsonify({"msg": "Circular dependency detected"}), 400

    # Use ORM to create a new task record
    session = SessionLocal()
    try:
        new_task = TaskModel(
            task_id=task_id,
            task_name=task_name,
            description=description,
            task_type=task_type,
            execution_params=json.dumps(execution_params),
            scheduling_rule=json.dumps(scheduling_rule),
            priority=priority,
            dependencies=json.dumps(dependencies)
        )
        session.add(new_task)
        session.commit()
    finally:
        session.close()

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
@jwt_required()
def get_tasks():
    """
    Retrieve all tasks using ORM and combine with Redis status.
    """
    session = SessionLocal()
    try:
        # Query all tasks via SQLAlchemy
        tasks = session.query(TaskModel).all()
    finally:
        session.close()

    task_list = []
    for t in tasks:
        task_dict = {
            "task_id": t.task_id,
            "task_name": t.task_name,
            "description": t.description,
            "task_type": t.task_type,
            "execution_params": json.loads(t.execution_params),
            "scheduling_rule": json.loads(t.scheduling_rule),
            "priority": t.priority,
            "dependencies": json.loads(t.dependencies) if t.dependencies else [],
            "status": redis_client.hget(t.task_id, "status") or b"unknown"
        }
        task_list.append(task_dict)

    # Decode the status from bytes to string
    for d in task_list:
        if isinstance(d["status"], bytes):
            d["status"] = d["status"].decode()

    return jsonify(task_list), 200


@app.route('/tasks/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """
    Delete an existing task by ID via ORM and remove from Redis + scheduler.
    """
    # Remove task from scheduler
    scheduler.remove_job(task_id)

    # Delete task using ORM
    session = SessionLocal()
    try:
        obj = session.query(TaskModel).filter_by(task_id=task_id).first()
        if obj:
            session.delete(obj)
            session.commit()
        else:
            return jsonify({"msg": "Task not found"}), 404
    finally:
        session.close()

    # Delete task from Redis
    redis_client.delete(task_id)

    return jsonify({"msg": "Task deleted successfully"}), 200


# ==========================
#      TASK EXECUTION
# ==========================
def execute_task(task_id, retry_count=0, max_retries=3):
    """
    Execute the given task and manage retries if it fails.
    """
    global concurrent_tasks
    with concurrent_lock:
        if concurrent_tasks >= MAX_CONCURRENT_TASKS:
            logging.info(f"Task {task_id} is waiting due to concurrent task limit.")
            return
        concurrent_tasks += 1

    task_info = redis_client.hgetall(task_id)
    task_info = {k.decode(): v.decode() for k, v in task_info.items()}
    task_type = task_info['task_type']
    execution_params = json.loads(task_info['execution_params'])
    dependencies = json.loads(task_info['dependencies'])

    # Check dependencies before executing
    for dep in dependencies:
        dep_status = redis_client.hget(dep, "status")
        if dep_status is None or dep_status.decode() != 'completed':
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
    Check for circular dependencies.
    """
    visited = set()
    stack = [task_id]

    while stack:
        current_task = stack.pop()
        if current_task in visited:
            return True
        visited.add(current_task)
        dep_json = redis_client.hget(current_task, "dependencies")
        if dep_json:
            sub_deps = json.loads(dep_json.decode())
            stack.extend(sub_deps)

    return False


def notify(task_id, status, error_info):
    """
    Notify about task completion or failure.
    """
    task_info = redis_client.hgetall(task_id)
    task_info = {k.decode(): v.decode() for k, v in task_info.items()}
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
    """Render the main interface for the task scheduler."""
    return render_template('index.html')


@app.route('/ui/tasks', methods=['GET'])
@jwt_required()
def tasks_ui():
    """Display all tasks in an HTML table using ORM data."""
    session = SessionLocal()
    try:
        tasks = session.query(TaskModel).all()
    finally:
        session.close()

    task_list = []
    for t in tasks:
        status_value = redis_client.hget(t.task_id, "status") or b"unknown"
        status_str = status_value.decode()
        task_info = {
            "task_id": t.task_id,
            "task_name": t.task_name,
            "description": t.description,
            "task_type": t.task_type,
            "execution_params": json.loads(t.execution_params) if t.execution_params else {},
            "scheduling_rule": json.loads(t.scheduling_rule) if t.scheduling_rule else {},
            "priority": t.priority,
            "dependencies": json.loads(t.dependencies) if t.dependencies else [],
            "status": status_str
        }
        task_list.append(task_info)

    return render_template('tasks.html', tasks=task_list)


@app.route('/ui/metrics', methods=['GET'])
@jwt_required()
def metrics_ui():
    """Show system resource metrics from the database via ORM."""
    session = SessionLocal()
    try:
        data = session.query(TaskModel).all()  # This is for tasks, but we want metrics, so let's fetch SystemMetric
    finally:
        session.close()

    # Let's correct that to show system metrics:
    # Or we can do a separate route for the actual system metrics table
    # For demonstration, we can query the SystemMetric model:
    from models import SystemMetric
    session = SessionLocal()
    try:
        metrics = session.query(SystemMetric).order_by(SystemMetric.id.desc()).limit(10).all()
    finally:
        session.close()

    # Prepare data for the template
    metrics_data = []
    for m in metrics:
        metrics_data.append([m.created_at, m.cpu_usage, m.memory_usage])

    return render_template('metrics.html', metrics=metrics_data)


# ==========================
#    SCHEDULE MONITORING
# ==========================
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
