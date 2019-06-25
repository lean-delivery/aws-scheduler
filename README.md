# aws-scheduler
Tiny UI for working in pair with [AWS instance scheduler](https://docs.aws.amazon.com/solutions/latest/instance-scheduler/welcome.html) for managing AWS resources start/stop schedule (ec2, rds) which respectively reduces costs.

#### Overview
**[AWS instance scheduler](https://docs.aws.amazon.com/solutions/latest/instance-scheduler/welcome.html)** operates over special tags to start or stop appropriate ec2/rds instances, and **aws-scheduler** is aimed to display, set and remove these tags in user-friendly way.
**aws-scheduler** is a Flask application which main function is add/remove/change tags on EC2/RDS instances in AWS.

This is how it looks like when you are an anonymous user (or not logged in yet). You can only view current schedules and instance that are set to those schedules:
![](https://i.ibb.co/p0yVJyk/1.jpg)

But after you logged in - managing is available and you can add/remove instances to different schedules:
![](https://i.ibb.co/2MwMQ1Z/3.jpg)

There can be multiple users with different access rights. For example on the next screenshot you can see that "user3" is restricted to manage some instances: 
![](https://i.ibb.co/z7fbp5d/4.jpg)

There might be cases when instance is managed by several users and you, as admin, want that instance to have the default schedule and force to set it back daily.
This is where so-called "scheduled task" comes on stage. 
There is an "instance-scheduler-default-schedules" table in DynamoDB which stores info about instances and their default schedules. 
"Scheduled task" runs daily within the application, retrieves information from this table and resets tags on instances according to this info.  


**Each instance can be included only in one schedule.**

Principal scheme:
![](https://i.ibb.co/SfLmrxn/aws-scheduler.jpg)

#### Installation
**For using **aws-scheduler** you must have [AWS instance scheduler](https://docs.aws.amazon.com/solutions/latest/instance-scheduler/welcome.html) installed and configured.**
1. Checkout code
2. Build docker image using Dockerfile and push it to registry
3. Run init script to create necessary Dynamo DB tables to store users, groups and default schedules
4. Use terraform plan to deploy docker image into AWS ECS

Init script creates tables:
* **instance-scheduler-users** - login, password, and groups in which user is included
* **instance-scheduler-groups** - group name and ec2 filters which are used for filtering results, this fields matched with the "group" field from **instance-scheduler-users** table. Filters field is a list of filters for boto3 in pythonic way. E.g. filter instances by name: \[{'Values': \["prefix1-\*", "prefix2-\*", "prefix3-\*", "PREFIX4-\*", "env_name"], 'Name': 'tag:Name'}] 
* **instance-scheduler-default-schedules** - default schedules for instances

#### Access rights
**instance-scheduler-users** table's "groups" field is matched with **instance-scheduler-groups** table. Each user can be included into multiple groups. So, access matrix for each user can be individual and flexible.

When new user is registered, appropriate fields are created in **instance-scheduler-users** table and group with username's name and username's filter fields is created in the **instance-scheduler-groups** table. It means that new user will be able to manage only instances with the same name as his login.    
 