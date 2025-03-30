import os
import json
import redis
import mysql.connector
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import threading
import requests
import smtplib
from email.mime.text import MIMEText
import logging

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'super-secret-key'
jwt = JWTManager(app)
scheduler = BackgroundScheduler()
redis_client = redis.Redis(host='localhost', port=6379, db=0)
mysql_conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='password',
    database='task_scheduler'
)
mysql_cursor = mysql_conn.cursor()
MAX_CONCURRENT_TASKS = 5
concurrent_tasks = 0
concurrent_lock = threading.Lock()

# Logging configuration
logging.basicConfig(filename='task_scheduler.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    # Here we assume simple username and password check, in real - world, use database
    if username == 'admin' and password == 'password':
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200
    return jsonify({"msg": "Invalid username or password"}), 401


@app.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
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

    # Store task in MySQL
    sql = "INSERT INTO tasks (task_id, task_name, description, task_type, execution_params, scheduling_rule, priority, dependencies) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    val = (task_id, task_name, description, task_type, json.dumps(execution_params), json.dumps(scheduling_rule), priority, json.dumps(dependencies))
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

    # Add task to scheduler
    trigger = get_trigger(scheduling_rule)
    scheduler.add_job(execute_task, trigger=trigger, args=[task_id], id=task_id)
    return jsonify({"msg": "Task created successfully"}), 201


@app.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
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
    return jsonify(task_list), 200


@app.route('/tasks/<task_id>', methods=['PUT'])
@jwt_required()
def modify_task(task_id):
    data = request.get_json()
    if 'scheduling_rule' in data:
        new_scheduling_rule = data['scheduling_rule']
        trigger = get_trigger(new_scheduling_rule)
        scheduler.reschedule_job(task_id, trigger=trigger)
        # Update in MySQL
        sql = "UPDATE tasks SET scheduling_rule = %s WHERE task_id = %s"
        val = (json.dumps(new_scheduling_rule), task_id)
        mysql_cursor.execute(sql, val)
        mysql_conn.commit()
        # Update in Redis
        redis_client.hset(task_id, "scheduling_rule", json.dumps(new_scheduling_rule))
    if 'execution_params' in data:
        new_execution_params = data['execution_params']
        # Update in MySQL
        sql = "UPDATE tasks SET execution_params = %s WHERE task_id = %s"
        val = (json.dumps(new_execution_params), task_id)
        mysql_cursor.execute(sql, val)
        mysql_conn.commit()
        # Update in Redis
        redis_client.hset(task_id, "execution_params", json.dumps(new_execution_params))
    return jsonify({"msg": "Task modified successfully"}), 200


@app.route('/tasks/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    scheduler.remove_job(task_id)
    # Delete from MySQL
    sql = "DELETE FROM tasks WHERE task_id = %s"
    val = (task_id,)
    mysql_cursor.execute(sql, val)
    mysql_conn.commit()
    # Delete from Redis
    redis_client.delete(task_id)
    return jsonify({"msg": "Task deleted successfully"}), 200


def execute_task(task_id):
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
            subprocess.run(['python'] + execution_params)
        elif task_type == 'api':
            method = execution_params.get('method', 'GET')
            url = execution_params.get('url')
            headers = execution_params.get('headers', {})
            data = execution_params.get('data', {})
            if method == 'GET':
                requests.get(url, headers=headers)
            elif method == 'POST':
                requests.post(url, headers=headers, data=data)
    except Exception as e:
        logging.error(f"Task {task_id} failed with error: {str(e)}")
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
    rule_type = scheduling_rule.get('type')
    if rule_type == 'fixed_time':
        return DateTrigger(run_date=scheduling_rule['run_date'])
    elif rule_type == 'interval':
        return IntervalTrigger(**scheduling_rule['interval'])
    elif rule_type == 'cron':
        return CronTrigger(**scheduling_rule['cron'])


def check_circular_dependency(task_id, dependencies):
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
    task_info = redis_client.hgetall(task_id)
    task_info = {key.decode(): value.decode() for key, value in task_info.items()}
    task_name = task_info['task_name']
    message = f"Task {task_name} ({task_id}) {status}"
    if status == 'failed':
        message += f" with error: {error_info}"
    # Send email notification
    msg = MIMEText(message)
    msg['Subject'] = f"Task {task_id} {status}"
    msg['From'] = 'sender@example.com'
    msg['To'] = 'recipient@example.com'
    server = smtplib.SMTP('smtp.example.com', 587)
    server.starttls()
    server.login('sender@example.com', 'password')
    server.sendmail('sender@example.com', 'recipient@example.com', msg.as_string())
    server.quit()


if __name__ == '__main__':
    scheduler.start()
    app.run(debug=True)

