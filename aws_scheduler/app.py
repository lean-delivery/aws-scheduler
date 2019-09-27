import os
from datetime import datetime, timezone, timedelta

import boto3
from botocore.exceptions import ClientError
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

from flask_expects_json import expects_json
from . import sch_vars


# json validation
set_tag_schema = {
    'type': 'object',
    'properties': {
        'Key': {'type': 'string'},
        'Value': {'type': 'string'}
    },
    'required': ['Key', 'Value']
}

remove_tag_schema = {
    'type': 'array',
    'items': {
        'type': 'string'
    }
}


# create connections to AWS
def create_aws_connections():
    dynamodb_resource = boto3.resource('dynamodb', region_name=sch_vars.REGION_DYNAMO_DB)

    regions_ec2_dict = {}
    for region in sch_vars.REGIONS_EC2:
        regions_ec2_dict[region] = boto3.client('ec2', region_name=region)

    rds_dict = {}
    for region in sch_vars.REGIONS_RDS:
        rds_dict[region] = boto3.client('rds', region_name=region)

    return dynamodb_resource, regions_ec2_dict, rds_dict


DYNAMODB_RESOURCE, EC2_CLIENTS, RDS_CLIENTS = create_aws_connections()
MULTI_REGIONAL = len(sch_vars.REGIONS_EC2) > 1  # flag to define if app is used in multiple or single region in aws

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


# return list<dict>, much easier to work with this method
def get_user_filters_v2():
    filters = []
    if session:
        groups = db_get_item(sch_vars.USERS_TABLE_NAME, {"username": session['username']})['Item']['groups']
        for group in groups:
            for filter in db_get_item(sch_vars.GROUPS_TABLE_NAME, {'group_name': group})['Item']['filters']:
                filters.append(filter)
    return filters


# return list<list<dict>>, better to move to v2 version
def get_user_filters():
    filters = []
    if session:
        groups = db_get_item(sch_vars.USERS_TABLE_NAME, {"username": session['username']})['Item']['groups']
        for group in groups:
            filters.append(db_get_item(sch_vars.GROUPS_TABLE_NAME, {'group_name': group})['Item']['filters'])
    return filters


def filtered(tags):
    for tag in tags:
        for value in tag.values():
            if any(filter_pattern in value for filter_pattern in sch_vars.NAME_FILTER_EXCLUDE_PATTERNS):
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
        filters.append({'Name': 'instance-state-name', 'Values': sch_vars.STATE_FILTER_INCLUDE_PATTERNS})  # add state filters
        try:
            for region_name, ec2_client in EC2_CLIENTS.items():
                for reservation in ec2_client.describe_instances(Filters=filters)["Reservations"]:
                    for instance in reservation["Instances"]:
                        if "Tags" in instance:
                            if filtered(instance["Tags"]):  # filter unwanted instances
                                continue
                            instance["InstanceName"] = get_tag(instance["Tags"], "Name")  # for convenience move Name tag to dedicated dict key
                            instance["Schedule"] = get_tag(instance["Tags"], "Schedule")  # for convenience move Schedule tag to dedicated dict key
                        else:  # if no tags found - create tags with special phrases
                            instance["InstanceName"] = "INSTANCE WITH NO TAGS"
                            instance["Schedule"] = "INSTANCE WITH NO TAGS"
                        if MULTI_REGIONAL:  # add region name to instance name if app is used in multiple regions
                            instance["InstanceName"] = "{0} ({1})".format(instance["InstanceName"], region_name)
                        yield {"InstanceId": instance["InstanceId"],
                               "InstanceName": instance["InstanceName"],
                               "Schedule": instance["Schedule"],
                               "Region": region_name}
        except ClientError as err:
            if err.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                continue
            else:
                app.logger.error(err)


def rds_instances(all_instances=False):
    filters = [] if all_instances else get_user_filters_v2()
    for region_name, rds_client in RDS_CLIENTS.items():
        try:
            for db_instance in rds_client.describe_db_instances()["DBInstances"]:
                if db_instance['DBInstanceStatus'] not in sch_vars.RDS_STATE_FILTER_INCLUDE_PATTERNS:
                    continue
                rds_tags = rds_client.list_tags_for_resource(ResourceName=db_instance['DBInstanceArn'])['TagList']
                db_instance["InstanceName"] = db_instance['DBInstanceIdentifier']
                db_instance["Schedule"] = next((rds_tag for rds_tag in rds_tags if rds_tag['Key'] == 'Schedule'), {}).get("Value", "INSTANCE WITH NO TAGS")
                if filters and not any(any(rds_tag['Key'] == filter['Name'] for rds_tag in rds_tags) and any(rds_tag['Value'] in filter['Values'] for rds_tag in rds_tags) for filter in filters):
                    continue
                if MULTI_REGIONAL:
                    db_instance["InstanceName"] = "{0} ({1})".format(db_instance["DBInstanceIdentifier"], region_name)
                yield {
                    "DBInstanceArn": db_instance["DBInstanceArn"],
                    "InstanceId": db_instance["DBInstanceIdentifier"],
                    "InstanceName": db_instance["InstanceName"],
                    "Schedule": db_instance["Schedule"],
                    "Region": region_name
                }
        except ClientError as err:
            if err.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                continue
            else:
                app.logger.error(err)


def remove_tag_from_ec2_instance(instance_id, instance_region, tag_name=sch_vars.DEFAULT_SCHEDULE_TAG_NAME):
    return EC2_CLIENTS[instance_region].delete_tags(Resources=[instance_id], Tags=[{"Key": tag_name}])


def add_tag_to_ec2_instance(instance_id, instance_region, schedule_name, tag_name=sch_vars.DEFAULT_SCHEDULE_TAG_NAME):
    return EC2_CLIENTS[instance_region].create_tags(Resources=[instance_id], Tags=[{"Key": tag_name, "Value": schedule_name}])


def return_default_tag_to_instances():
    table = DYNAMODB_RESOURCE.Table(sch_vars.DEFAULT_SCHEDULES_TABLE_NAME)
    for item in table.scan()["Items"]:
        if "default_schedule" not in item:
            app.logger.error('Unable to return default schedule tag to instance(s) %s because schedule field is empty in database', item["instance_name"])
            continue
        response = (EC2_CLIENTS[item["region_name"]].describe_instances(Filters=[{"Name": "tag:Name", "Values": [item["instance_name"]]}]))
        if len(response["Reservations"]) == 0:
            app.logger.error('Unable to return default schedule tag to instance(s) %s because no instance(s) with such name found', item["instance_name"])
            continue
        else:
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    response = add_tag_to_ec2_instance(instance["InstanceId"], item["region_name"], item["default_schedule"])
                    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                        app.logger.info('Default tag %s returned to instance %s', item["default_schedule"], item["instance_name"])
                    else:
                        app.logger.error('Return default schedule tag to instance %s error: %s', item["instance_name"], response["ResponseMetadata"])


def set_up_default_tag():
    for region_name, ec2_client in EC2_CLIENTS.items():
        for reservation in ec2_client.describe_instances()["Reservations"]:
            for instance in reservation["Instances"]:
                if "Tags" in instance:
                    tags = instance["Tags"]
                    launch_time_with_deploy_delay = instance["LaunchTime"] + timedelta(hours=3)
                    if datetime.now(timezone.utc) > launch_time_with_deploy_delay and not any(tag["Key"] == "Schedule" for tag in tags):
                        ec2_client.create_tags(
                            Resources=[instance["InstanceId"]],
                            Tags=[{'Key': sch_vars.DEFAULT_SCHEDULE_TAG_NAME, 'Value': sch_vars.DEFAULT_SCHEDULE_TAG_VALUE}]
                        )


def schedules_combined_with_periods():
    schedules = []
    for schedule in db_query(sch_vars.CONFIG_TABLE_NAME, type="schedule")['Items']:
        periods = []
        if "periods" in schedule:
            for period in schedule['periods']:
                periods += db_query(sch_vars.CONFIG_TABLE_NAME, type='period', name=period)["Items"]
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


def schedules_combined_with_periods_and_rds_instances():
    instances_readonly = sorted([i for i in rds_instances(all_instances=True)], key=lambda k: k['InstanceName'])
    if session:
        instances_manageable = sorted([i for i in rds_instances(all_instances=False)], key=lambda k: k['InstanceName'])
        instances_readonly = [item for item in instances_readonly if item not in instances_manageable]
    schedules = schedules_combined_with_periods()

    for schedule in schedules:
        if session:
            rds_instances_manageable_temp_list = []
            for instance in instances_manageable:
                if instance["Schedule"] == schedule["name"]:
                    rds_instances_manageable_temp_list.append(instance)
                    continue
            schedule.update({"rds_instances_manageable": rds_instances_manageable_temp_list})

        rds_instances_readonly_temp_list = []
        for instance in instances_readonly:
            if instance["Schedule"] == schedule["name"]:
                rds_instances_readonly_temp_list.append(instance)
                continue
        schedule.update({"rds_instances_readonly": rds_instances_readonly_temp_list})

    if session:
        return schedules, instances_manageable
    return schedules, []


def validate_username_length(username):
    return len(username) == sch_vars.USERNAME_LENGHT_FILTERS


def validate_username_name_convention(username):
    return username.lower().startswith(sch_vars.USERNAME_REGISTER_FILTERS)


def validate_username_exist(username):
    return "Item" not in db_get_item(sch_vars.USERS_TABLE_NAME, {"username": username})


@app.route('/')
def index():
    schedules, instances = schedules_combined_with_periods_and_ec2instances()
    return render_template('index.html', schedules=schedules, instances=instances)


@app.route('/rds')
def rds_index():
    schedules, instances = schedules_combined_with_periods_and_rds_instances()
    return render_template('rds.html', schedules=schedules, instances=instances)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template('login.html')
    elif request.method == "POST":
        response = db_get_item(sch_vars.USERS_TABLE_NAME, {"username": request.form['username']})
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
            ret_str = "Please use your " + str(sch_vars.PROJECT_NAME) + " login for register ("+ str(sch_vars.USERNAME_LENGHT_FILTERS) +" simbols). i.e '" + str(sch_vars.USERNAME_REGISTER_FILTERS[0]) + "' + 5 symbols name abbreviation"
            return ret_str
        if not validate_username_exist(request.form['username']):
            return "Username already exists"
        if request.form['password'] == request.form['password2']:
            db_put_item(sch_vars.USERS_TABLE_NAME, {'username': request.form['username'], 'password': hash_password(request.form['password']), 'groups': [request.form['username']]})
            db_put_item(sch_vars.GROUPS_TABLE_NAME, {'group_name': request.form['username'], 'filters': [{'Values': ["dev_{0}".format(request.form['username'])], 'Name': 'tag:Name'}]})
            app.logger.info('%s registered successfully', request.form['username'])
            return redirect(url_for('index'))
        else:
            return "You've entered different passwords"


@app.route('/remove_tag', methods=['POST'])
@login_required
def remove():
    if request.method == "POST":
        response = remove_tag_from_ec2_instance(request.form['instance_id'], request.form['instance_region'])
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            app.logger.info('instance %s in region %s was removed from schedule by %s', request.form['instance_id'], request.form['instance_region'], session['username'])
            return redirect(url_for('index'))
        else:
            return response


@app.route('/add_tag', methods=['POST'])
@login_required
def add():
    if request.method == "POST":
        instance_id, region = request.form['instance_id'].split()  # TODO: need to refactor frontend to send this in separate variables
        response = add_tag_to_ec2_instance(instance_id, region, request.form['schedule_name'])
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            app.logger.info('instance %s in region %s was added to %s schedule by %s', instance_id, region, request.form['schedule_name'], session['username'])
            return redirect(url_for('index'))
        else:
            return response


@expects_json(set_tag_schema)
@app.route(
    '/rds/regions/<string:region_id>/instances/<string:instance_id>/tags/add',
    methods=['POST']
)
@login_required
def set_tag(region_id, instance_id):
    json_content = request.get_json()
    response = RDS_CLIENTS[region_id].add_tags_to_resource(ResourceName=instance_id, Tags=[json_content])
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        app.logger.info('instance %s in region %s was added to %s schedule by %s', instance_id, region_id, request.form['schedule_name'], session['username'])
        return redirect(url_for('rds_index'))
    else:
        return response


@expects_json(remove_tag_schema)
@app.route(
    '/rds/regions/<string:region_id>/instances/<string:instance_id>/tags/remove',
    methods=['POST']
)
@login_required
def remove_tag(region_id, instance_id):
    json_content = request.get_json()
    response = RDS_CLIENTS[region_id].remove_tags_from_resource(ResourceName=instance_id, TagKeys=json_content)
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        app.logger.info('instance %s in region %s was added to %s schedule by %s', instance_id, region_id, request.form['schedule_name'], session['username'])
        return redirect(url_for('rds_index'))
    else:
        return response


# Add background job(s)
scheduler = BackgroundScheduler()
scheduler.add_job(func=return_default_tag_to_instances, trigger="cron", hour=sch_vars.CRON_START_HOUR, minute=sch_vars.CRON_START_MINUTE, timezone=sch_vars.CRON_TIMEZONE, id='return_default_tag_to_instances')
scheduler.add_job(func=set_up_default_tag, trigger="interval", minutes=60, id='set_up_default_tag')
scheduler.start()
atexit.register(lambda: scheduler.shutdown())  # Shut down the scheduler when exiting the app
