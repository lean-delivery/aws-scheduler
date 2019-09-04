import boto3
import sch_vars


region = sch_vars.region
aws_access_key_id = sch_vars.aws_access_key_id
aws_secret_access_key = sch_vars.aws_secret_access_key

table_name_users = sch_vars.USERS_TABLE_NAME
table_name_groups = sch_vars.GROUPS_TABLE_NAME
table_name_default_schedules = sch_vars.DEFAULT_SCHEDULES_TABLE_NAME

dynamodb_resource = boto3.resource('dynamodb', region_name=region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)


def create_table(table_name, primary_key):
    table = dynamodb_resource.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': primary_key,
                'KeyType': 'HASH'
            },
        ],
        AttributeDefinitions=[
            {
                'AttributeName': primary_key,
                'AttributeType': 'S'
            },
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )

    # Wait until the table exists.
    table.meta.client.get_waiter('table_exists').wait(TableName=table_name)

    # Print out some data about the table.
    print(table.item_count)


create_table(table_name_users, "username")
create_table(table_name_groups, "group_name")
create_table(table_name_default_schedules, "instance_name")
