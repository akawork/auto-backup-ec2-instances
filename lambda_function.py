"""
Main lambda function
"""

import datetime
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

COUNTER = {
    "snapshot_created": 0,
    "snapshot_created_size": 0,
    "snapshot_deleted": 0,
    "snapshot_deleted_size": 0
}


class Snapshot():
    """
    handle all action with snapshot
    """

    def __init__(self, ec2):
        """
        Init method
        """
        self.ec2 = ec2

    @staticmethod
    def get_instances(ec2):
        """
        Get all instances
        """
        # We only want to look through instances with
        # the following tag key value pair: auto_snapshot : true
        instances = ec2.instances.filter(Filters=[{
            'Name': 'tag:auto_backup',
            'Values': ['true']
        }])
        return instances

    @staticmethod
    def find_tag(instance, tag_value):
        """
        find the instance tag name
        """
        for tag in instance.tags:  # Get the name of the instance
            if tag['Key'] == tag_value:
                tag_name_value = tag['Value']
        print('[+] Found tagged instance \'{1}\', id: {0}, state: {2}'.format(
            instance.id, tag_name_value, instance.state['Name']))
        return tag_name_value

    @staticmethod
    def create_snapshot(vol, tag_name_value):
        """
        Create snapshot of volume match with tag name
        """
        print(
            '[+] {0} is attached to volume {1}, proceeding to snapshot'.format(
                tag_name_value, vol.id))

        snapshot = vol.create_snapshot(
            Description='Auto Backup of {0}, on volume {1} - Created {2}'.
            format(tag_name_value, vol.id, TODAY_STRING), )
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
                '{}-autobackup'.format(tag_name_value) + '-' + TODAY_STRING
            }])

        print("[+] Snapshot completed")
        COUNTER["snapshot_created"] += 1
        COUNTER["snapshot_created_size"] = snapshot.volume_size

    @staticmethod
    def delete_snapshot(snapshot):
        """
        Delete snapshot out of date
        """
        can_delete = False
        for tag in snapshot.tags:  # Use these if statements to get each snapshot's
            # cleated on date, name and auto_snap tag
            if tag['Key'] == 'CreatedOn':
                created_on_string = tag['Value']
            if tag['Key'] == 'auto_backup' and tag['Value'] == 'true':
                can_delete = True
            if tag['Key'] == 'Name':
                name = tag['Value']
        created_on = datetime.datetime.strptime(
            created_on_string, '%Y/%m/%d').date()

        if created_on <= DELETION_DATE and can_delete:
            print(
                '[+] Snapshot id {0}, ({1}) from {2} is {3} or more days old... deleting'
                .format(snapshot.id, name, created_on_string,
                        DELETE_AFTER_DAY))
            response = snapshot.delete()
            if response:
                COUNTER["snapshot_deleted"] += snapshot.volume_size
                COUNTER["snapshot_deleted_size"] += 1

    def create_all_snapshot(self):
        """
        Create snapshot for instance
        """

        ec2 = self.ec2
        instances = Snapshot.get_instances(ec2)

        for _inst in instances.all():
            tag_name_value = Snapshot.find_tag(_inst, 'Name')

            # Iterate through each instance's volumes
            vols = _inst.volumes.all()
            for vol in vols:
                Snapshot.create_snapshot(vol, tag_name_value)


    def delete_all_snapshot(self):
        """
        Delete all snapshot out of date
        """
        ec2 = self.ec2
        instances = Snapshot.get_instances(ec2)

        for _inst in instances.all():

            tag_name_value = Snapshot.find_tag(_inst, 'Name')

            # Now iterate through snapshots which were made by autsnap
            snapshots = ec2.snapshots.filter(Filters=[{
                'Name': 'tag:auto_backup',
                'Values': ['true']
            }])

            print('[+] Checking for out of date snapshots for instance {0}...'.
                  format(tag_name_value))
            for snapshot in snapshots:
                Snapshot.delete_snapshot(snapshot)


def lambda_handler(event, context):
    """
    Handle when have event
    """

    for _reg in ALL_REGIONS:
        print('[+] Instances in EC2 Region {0}:'.format(_reg))
        ec2 = boto3.resource('ec2', region_name=_reg)
        snapshot = Snapshot(ec2)
        snapshot.create_all_snapshot()
        snapshot.delete_all_snapshot()

    print('[+] Result:')
    print(
        ' Total snapshot created: {0}\n Total size of snapshots created: {1} GB'
        .format(COUNTER["snapshot_created"], COUNTER["snapshot_created_size"]))

    print(
        ' Total snapshot deleted: {0}\n Total size of snapshots deleted {1} GB'
        .format(COUNTER["snapshot_deleted"], COUNTER["snapshot_deleted_size"]))

    return
