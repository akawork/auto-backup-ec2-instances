"""
Main lambda function
"""

import datetime
import time
import sys
import boto3

TODAY = datetime.date.today()
TODAY_STRING = TODAY.strftime('%Y/%m/%d')
DELETE_AFTER_DAY = 3  # Delete snapshots after this many days

# Except after Monday (at Tuesday ~1am), since Friday is only 2 'working' days away:
if datetime.date.today().weekday() == 1:
    DELETE_AFTER_DAY = DELETE_AFTER_DAY + 2

DELETION_DATE = TODAY - datetime.timedelta(days=DELETE_AFTER_DAY)
DELETION_DATE_STRING = DELETION_DATE.strftime('%Y/%m/%d')

EC2 = boto3.client('ec2')
REGION = EC2.describe_regions().get('Regions', [])
# with region is ['RegionName'] for region in regions
ALL_REGIONS = ['ap-northeast-2']

SNAPSHOT_COUNTER = 0
SNAPSHOT_SIZE_COUNTER = 0
DELETION_COUNTER = 0
DELETED_SIZE_COUNTER = 0

"""
handle all action with snapshot
"""
class Snapshot(object):
    def create(self, _region):
        """
        Create snapshot for instance
        """
        print('[+] Instances in EC2 Region {0}:'.format(_region))
        ec2 = boto3.resource('ec2', region_name=_region)

        # We only want to look through instances with
        # the following tag key value pair: auto_snapshot : true
        instances = ec2.instances.filter(Filters=[{
            'Name': 'tag:auto_backup',
            'Values': ['true']
        }])

        volume_ids = []
        for _inst in instances.all():

            for tag in _inst.tags:  # Get the name of the instance
                if tag['Key'] == 'Name':
                    name = tag['Value']

            print('[+] Found tagged instance \'{1}\', id: {0}, state: {2}'.format(
                _inst.id, name, _inst.state['Name']))

						# Iterate through each instance's volumes
            vols = _inst.volumes.all()
            for vol in vols:
                print('[+] {0} is attached to volume {1}, proceeding to snapshot'.
                      format(name, vol.id))
                volume_ids.extend(vol.id)
                snapshot = vol.create_snapshot(
                    Description=
                    'Auto Backup of {0}, on volume {1} - Created {2}'.format(
                        name, vol.id, TODAY_STRING), )
                snapshot.create_tags(  # Add the following tags to the new snapshot
                    Tags=[{
                        'Key': 'auto_backup',
                        'Value': 'true'
                    }, {
                        'Key': 'volume',
                        'Value': vol.id
                    }, {
                        'Key': 'CreatedOn',
                        'Value': TODAY_STRING
                    }, {
                        'Key':
                        'Name',
                        'Value':
                        '{}-autobackup'.format(name) + '-' + TODAY_STRING
                    }])
                print('[+] Snapshot completed')
                # SNAPSHOT_COUNTER += 1
                # SNAPSHOT_SIZE_COUNTER += snapshot.volume_size

    def delete(self, region):
        """
        Create snapshot for instance
        """
        print('[+] Instances in EC2 Region {0}:'.format(region))
        ec2 = boto3.resource('ec2', region_name=region)

        # We only want to look through instances with
        # the following tag key value pair: auto_snapshot : true
        instances = ec2.instances.filter(Filters=[{
            'Name': 'tag:auto_backup',
            'Values': ['true']
        }])

        volume_ids = []
        for _inst in instances.all():

            for tag in _inst.tags:  # Get the name of the instance
                if tag['Key'] == 'Name':
                    name = tag['Value']

            print('[+] Found tagged instance \'{1}\', id: {0}, state: {2}'.format(
                _inst.id, name, _inst.state['Name']))

            vols = _inst.volumes.all(
            )  # Iterate through each instance's volumes
            for vol in vols:
                # Now iterate through snapshots which were made by autsnap
                snapshots = ec2.snapshots.filter(Filters=[{
                    'Name': 'tag:auto_backup',
                    'Values': ['true']
                }])

                print('[+] Checking for out of date snapshots for instance {0}...'.
                      format(name))
                for snap in snapshots:
                    can_delete = False
                    for tag in snap.tags:  # Use these if statements to get each snapshot's
                        # cleated on date, name and auto_snap tag
                        if tag['Key'] == 'CreatedOn':
                            created_on_string = tag['Value']
                        if tag['Key'] == 'auto_backup' and tag[
                                'Value'] == 'true':
                            can_delete = True
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                    created_on = datetime.datetime.strptime(
                        created_on_string, '%Y/%m/%d').date()

                    if created_on <= DELETION_DATE and can_delete:
                        print(
                            '[+] Snapshot id {0}, ({1}) from {2} is {3} or more days old... deleting'
                            .format(snap.id, name, created_on_string,
                                    DELETE_AFTER_DAY))
                        # DELETED_SIZE_COUNTER += snap.volume_size
                        snap.delete()
                        # DELETION_COUNTER += 1


def lambda_handler(event, context):
    """
    Handle when have event
    """
    snapshot = Snapshot()

    for _reg in ALL_REGIONS:
        snapshot.create(_reg)
        snapshot.delete(_reg)

    print('[+] Made {0} snapshots totalling {1} GB\
        Deleted {2} snapshots totalling {3} GB'.format(SNAPSHOT_COUNTER,
                                                       SNAPSHOT_SIZE_COUNTER,
                                                       DELETION_COUNTER,
                                                       DELETED_SIZE_COUNTER))
    return
