import os
import boto3
from boto3.dynamodb.conditions import Key
from flask import Flask
from flask import session
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash
from functools import wraps
import uuid
import hashlib
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from logging.config import dictConfig


# dynamodb connection config
CONFIG_TABLE_NAME = "instance-scheduler-ConfigTable"  # created when deploying aws instance scheduler
USERS_TABLE_NAME = "instance-scheduler-users"  # created by init script
GROUPS_TABLE_NAME = "instance-scheduler-groups"  # created by init script
DEFAULT_SCHEDULES_TABLE_NAME = "instance-scheduler-default-schedules"  # created by init script

# tagging config
DEFAULT_SCHEDULE_TAG_NAME = "Schedule"  # tag name to store "schedule name", configured when deploying aws instance scheduler

# filtering options
STATE_FILTER_INCLUDE_PATTERNS = ['pending', 'running', 'stopping', 'stopped', 'shutting-down']  # if ec2 machine is in any of these states - it is not filtered
NAME_FILTER_EXCLUDE_PATTERNS = ["CI", "terminated"]  # if ec2 machine name tag contain any of these string - it is filtered

# username requirements for new users
USERNAME_REGISTER_FILTERS = ()  # forbid using usernames which started with strings in this tuple, e.g ('euv', 'ruv'), if you don't have name convention restrictions just leave it empty
USERNAME_MIN_LENGTH = 8

# return default tag schedule task config
CRON_START_HOUR = 7
CRON_START_MINUTE = 45
CRON_TIMEZONE = "Europe/Minsk"

# aws connection config
region = "eu-central-1"
DYNAMODB_RESOURCE = boto3.resource('dynamodb', region_name=region)
EC2_CLIENT = boto3.client('ec2', region_name=region)


# change flask log output format
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)
app.secret_key = os.urandom(12)


def hash_password(password):
    # uuid is used to generate a random number
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt


def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def db_query(table_name, type=None, name=None):
    table = DYNAMODB_RESOURCE.Table(table_name)

    if type and name:
        filtering_exp = Key('type').eq(type) & Key('name').eq(name)
    elif type:
        filtering_exp = Key('type').eq(type)
    else:
        return None

    return table.query(KeyConditionExpression=filtering_exp)


def db_put_item(table_name, item):
    return DYNAMODB_RESOURCE.Table(table_name).put_item(Item=item)


def db_get_item(table_name, key):
    return DYNAMODB_RESOURCE.Table(table_name).get_item(Key=key)


def get_user_filters():
    filters = []
    if session:
        groups = db_get_item(USERS_TABLE_NAME, {"username": session['username']})['Item']['groups']
        for group in groups:
            filters.append(db_get_item(GROUPS_TABLE_NAME, {'group_name': group})['Item']['filters'])
    return filters


def filtered(tags):
    for tag in tags:
        for value in tag.values():
            if any(filter_pattern in value for filter_pattern in NAME_FILTER_EXCLUDE_PATTERNS):
                return True


def get_tag(tags, tag_name):
    for tag in tags:
        if tag["Key"] == tag_name:
            return tag["Value"]
    return "INSTANCE WITH NO {0} TAG".format(tag_name)


def ec2_instances(all_instances=False):
    if all_instances:
        list_of_filters = [
            []]  # need to iterate over list of filters, so to get all instances create list with only one empty list (empty list in filters means 'all instances')
    else:
        list_of_filters = get_user_filters()
    for filters in list_of_filters:
        filters.append({'Name': 'instance-state-name', 'Values': STATE_FILTER_INCLUDE_PATTERNS})  # add state filters
        for reservation in EC2_CLIENT.describe_instances(Filters=filters)["Reservations"]:
            for instance in reservation["Instances"]:
                if "Tags" in instance:
                    if filtered(instance["Tags"]):  # filter unwanted instances
                        continue
                    instance["InstanceName"] = get_tag(instance["Tags"], "Name")  # for convenience move Name tag to dedicated dict key
                    instance["Schedule"] = get_tag(instance["Tags"], "Schedule")  # for convenience move Schedule tag to dedicated dict key
                else:  # if no tags found - create tags with special phrases
                    instance["InstanceName"] = "INSTANCE WITH NO TAGS"
                    instance["Schedule"] = "INSTANCE WITH NO TAGS"
                yield {"InstanceId": instance["InstanceId"], "InstanceName": instance["InstanceName"], "Schedule": instance["Schedule"]}


def remove_tag_from_ec2_instance(instance_id, tag_name=DEFAULT_SCHEDULE_TAG_NAME):
    return EC2_CLIENT.delete_tags(Resources=[instance_id], Tags=[{"Key": tag_name}])


def add_tag_to_ec2_instance(instance_id, schedule_name, tag_name=DEFAULT_SCHEDULE_TAG_NAME):
    return EC2_CLIENT.create_tags(Resources=[instance_id], Tags=[{"Key": tag_name, "Value": schedule_name}])


def return_default_tag_to_instances():
    table = DYNAMODB_RESOURCE.Table(DEFAULT_SCHEDULES_TABLE_NAME)
    for item in table.scan()["Items"]:
        if "default_schedule" not in item:
            app.logger.error('Unable to return default schedule tag to instance(s) %s because schedule field is empty in database', item["instance_name"])
            continue
        response = (EC2_CLIENT.describe_instances(Filters=[{"Name": "tag:Name", "Values": [item["instance_name"]]}]))
        if len(response["Reservations"]) == 0:
            app.logger.error('Unable to return default schedule tag to instance(s) %s because no instance(s) with such name found', item["instance_name"])
            continue
        else:
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    response = add_tag_to_ec2_instance(instance["InstanceId"], item["default_schedule"])
                    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                        app.logger.info('Default tag %s returned to instance %s', item["default_schedule"], item["instance_name"])
                    else:
                        app.logger.error('Return default schedule tag to instance %s error: %s', item["instance_name"], response["ResponseMetadata"])


def schedules_combined_with_periods():
    schedules = []
    for schedule in db_query(CONFIG_TABLE_NAME, type="schedule")['Items']:
        periods = []
        if "periods" in schedule:
            for period in schedule['periods']:
                periods += db_query(CONFIG_TABLE_NAME, type='period', name=period)["Items"]
            if periods:
                schedule['periods'] = periods
        schedules.append(schedule)
    return schedules


def schedules_combined_with_periods_and_ec2instances(all_instances=False):
    instances_readonly = sorted([i for i in ec2_instances(all_instances=True)], key=lambda k: k['InstanceName'])
    if session:
        instances_manageable = sorted([i for i in ec2_instances(all_instances=all_instances)], key=lambda k: k['InstanceName'])
        instances_readonly = [item for item in instances_readonly if item not in instances_manageable]
    schedules = schedules_combined_with_periods()

    for schedule in schedules:
        if session:
            ec2_instances_manageable_temp_list = []
            for instance in instances_manageable:
                if instance["Schedule"] == schedule["name"]:
                    ec2_instances_manageable_temp_list.append(instance)
                    continue
            schedule.update({"ec2_instances_manageable": ec2_instances_manageable_temp_list})

        ec2_instances_readonly_temp_list = []
        for instance in instances_readonly:
            if instance["Schedule"] == schedule["name"]:
                ec2_instances_readonly_temp_list.append(instance)
                continue
        schedule.update({"ec2_instances_readonly": ec2_instances_readonly_temp_list})

    if session:
        return schedules, instances_manageable
    return schedules, []


def validate_username_length(username):
    return len(username) >= USERNAME_MIN_LENGTH


def validate_username_name_convention(username):
    return username.lower().startswith(USERNAME_REGISTER_FILTERS)


def validate_username_exist(username):
    return "Item" not in db_get_item(USERS_TABLE_NAME, {"username": username})


@app.route('/')
def index():
    schedules, instances = schedules_combined_with_periods_and_ec2instances()
    return render_template('index.html', schedules=schedules, instances=instances)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template('login.html')
    elif request.method == "POST":
        response = db_get_item(USERS_TABLE_NAME, {"username": request.form['username']})
        if "Item" in response:
            if check_password(response['Item']['password'], request.form['password']):
                session['logged_in'] = True
                session['username'] = request.form['username']
                app.logger.info('%s logged in successfully', request.form['username'])
                return redirect(url_for('index'))
            else:
                app.logger.warning('%s failed to log in', request.form['username'])
                flash('Wrong password')
        else:
            app.logger.warning('Someone tried to login with username %s, but it does not exist', request.form['username'])
            flash('Username does not exist')
        return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        return render_template('register.html')
    if request.method == "POST":
        if not validate_username_length(request.form['username']) or not validate_username_name_convention(request.form['username']):
            return "Username does not comply with name convention requirements"
        if not validate_username_exist(request.form['username']):
            return "Username already exists"
        if request.form['password'] == request.form['password2']:
            db_put_item(USERS_TABLE_NAME, {'username': request.form['username'], 'password': hash_password(request.form['password']), 'groups': [request.form['username']]})
            db_put_item(GROUPS_TABLE_NAME, {'group_name': request.form['username'], 'filters': [{'Values': ["{0}".format(request.form['username'])], 'Name': 'tag:Name'}]})
            app.logger.info('%s registered successfully', request.form['username'])
            return redirect(url_for('index'))
        else:
            return "You've entered different passwords"


@app.route('/remove_tag', methods=['POST'])
@login_required
def remove():
    if request.method == "POST":
        response = remove_tag_from_ec2_instance(request.form['instance_id'])
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            app.logger.info('instance %s was removed from schedule by %s', request.form['instance_id'], session['username'])
            return redirect(url_for('index'))
        else:
            return response


@app.route('/add_tag', methods=['POST'])
@login_required
def add():
    if request.method == "POST":
        response = add_tag_to_ec2_instance(request.form['instance_id'], request.form['schedule_name'])
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            app.logger.info('%s was added to %s schedule by %s', request.form['instance_id'], request.form['schedule_name'], session['username'])
            return redirect(url_for('index'))
        else:
            return response


# Add background job(s)
scheduler = BackgroundScheduler()
scheduler.add_job(func=return_default_tag_to_instances, trigger="cron", hour=CRON_START_HOUR, minute=CRON_START_MINUTE, timezone=CRON_TIMEZONE)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())  # Shut down the scheduler when exiting the app
