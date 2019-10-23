# vars for AWS creds
region = "eu-central-1"
aws_access_key_id = ""
aws_secret_access_key = ""


# There are variables for customization your scheduler
PROJECT_NAME = "ProjectName"
CONFIG_TABLE_NAME = PROJECT_NAME + "-instance-scheduler-ConfigTable-3WM26WVP6TBP"
USERS_TABLE_NAME = PROJECT_NAME + "-instance-scheduler-users"
GROUPS_TABLE_NAME = PROJECT_NAME + "-instance-scheduler-groups"
DEFAULT_SCHEDULES_TABLE_NAME = PROJECT_NAME + "-instance-scheduler-default-schedules"
STATE_FILTER_INCLUDE_PATTERNS = ['pending', 'running', 'stopping', 'stopped', 'shutting-down']  # if ec2 machine is in any of these states - it is not filtered
RDS_STATE_FILTER_INCLUDE_PATTERNS = ['available', 'starting', 'stopped', 'stopping']
NAME_FILTER_EXCLUDE_PATTERNS = ["CI", "terminated"]  # if ec2 machine name tag contain any of these string - it is filtered
CRON_START_HOUR = 7
CRON_START_MINUTE = 56
CRON_TIMEZONE = "Europe/Moscow"

# Login name filter (login should start from these prefixes)
# If you don't need this, use something like this ('',)
#USERNAME_REGISTER_FILTERS = ('',) 
USERNAME_REGISTER_FILTERS = ('prefix1', 'prefix2') 
# Expected lengh of login name
USERNAME_LENGHT_FILTERS = 8

DEFAULT_SCHEDULE_TAG_NAME = "Schedule"
DEFAULT_SCHEDULE_TAG_VALUE = "daily_stop_21:00"

REGION_DYNAMO_DB = "eu-central-1"  # region where dynamodb tables for web app are stored
REGIONS_EC2 = ["eu-central-1", "us-east-1", "ap-south-1"]  # list of regions from which ec2 instances will be displayed
REGIONS_RDS = ["eu-central-1", "us-east-1", "ap-south-1"]  # list of regions from which rds instances will be displayed
