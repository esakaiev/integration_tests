import argparse
import sys
import time
from datetime import datetime
from datetime import timedelta

from tabulate import tabulate

from cfme.utils.log import add_stdout_handler
from cfme.utils.log import logger
from cfme.utils.path import log_path
from cfme.utils.providers import get_mgmt
from cfme.utils.providers import list_provider_keys

add_stdout_handler(logger)


def parse_cmd_line():
    parser = argparse.ArgumentParser(argument_default=None)
    parser.add_argument('--exclude-volumes', nargs='+',
                        help='List of volumes, which should be excluded.')
    parser.add_argument('--exclude-eips', nargs='+',
                        help='List of EIPs, which should be '
                             'excluded. Allocation_id or public IP are allowed.')
    parser.add_argument('--exclude-elbs', nargs='+',
                        help='List of ELBs, which should be excluded.')
    parser.add_argument('--exclude-enis', nargs='+',
                        help='List of ENIs, which should be excluded. ENI ID is allowed.')
    parser.add_argument('--exclude_stacks', nargs='+',
                        help='List of Stacks, which should be excluded')
    parser.add_argument('--exclude_snapshots', nargs='+',
                        help='List of snapshots, which should be excluded. Snapshot ID is allowed')
    parser.add_argument('--exclude_queues', nargs='+',
                        help='List of queues, which should be excluded. Queue Url is allowed')
    parser.add_argument('--stack-template',
                        help='Stack name template to be removed', default="test", type=str)
    parser.add_argument("--output", dest="output", help="target file name, default "
                                                        "'cleanup_ec2.log' in utils.path.log_path",
                        default=log_path.join('cleanup_ec2.log').strpath)
    args = parser.parse_args()
    return args


def delete_disassociated_addresses(provider_mgmt, excluded_eips, output):
    ip_list = []
    provider_name = provider_mgmt.kwargs['name']
    try:
        for ip in provider_mgmt.get_all_disassociated_addresses():
            if ip.allocation_id:
                if excluded_eips and ip.allocation_id in excluded_eips:
                    logger.info("  Excluding allocation ID: %r", ip.allocation_id)
                    continue
                else:
                    ip_list.append([provider_name, ip.public_ip, ip.allocation_id])
                    provider_mgmt.release_vpc_address(alloc_id=ip.allocation_id)
            else:
                if excluded_eips and ip.public_ip in excluded_eips:
                    logger.info("  Excluding IP: %r", ip.public_ip)
                    continue
                else:
                    ip_list.append([provider_name, ip.public_ip, 'N/A'])
                    provider_mgmt.release_address(address=ip.public_ip)
        logger.info("  Released Addresses: %r", ip_list)
        if ip_list:
            with open(output, 'a+') as report:
                # tabulate ip_list and write it
                report.write(tabulate(tabular_data=ip_list,
                                      headers=['Provider Key', 'Public IP', 'Allocation ID'],
                                      tablefmt='orgtbl'))

    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_disassociated_addresses.__name__)


def delete_unattached_volumes(provider_mgmt, excluded_volumes, output):
    volume_list = []
    provider_name = provider_mgmt.kwargs['name']
    try:
        for volume in provider_mgmt.get_all_unattached_volumes():
            if excluded_volumes and volume.id in excluded_volumes:
                logger.info("  Excluding volume id: %r", volume.id)
                continue
            else:
                volume_list.append([provider_name, volume.id])
                volume.delete()
        logger.info("  Deleted Volumes: %r", volume_list)
        if volume_list:
            with open(output, 'a+') as report:
                # tabulate volume_list and write it
                report.write(tabulate(tabular_data=volume_list,
                                      headers=['Provider Key', 'Volume ID'],
                                      tablefmt='orgtbl'))
    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_unattached_volumes.__name__)


def delete_unused_loadbalancers(provider_mgmt, excluded_elbs, output):
    elb_list = []
    provider_name = provider_mgmt.kwargs['name']
    try:
        for elb in provider_mgmt.get_all_unused_loadbalancers():
            if excluded_elbs and elb.name in excluded_elbs:
                logger.info("  Excluding Elastic LoadBalancer id: %r", elb.name)
                continue
            else:
                elb_list.append([provider_name, elb.name])
                provider_mgmt.delete_loadbalancer(loadbalancer=elb)
        logger.info("  Deleted Elastic LoadBalancers: %r", elb_list)
        if elb_list:
            with open(output, 'a+') as report:
                # tabulate volume_list and write it
                report.write(tabulate(tabular_data=elb_list,
                                      headers=['Provider Key', 'ELB name'],
                                      tablefmt='orgtbl'))
    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_unused_loadbalancers.__name__)


def delete_unused_network_interfaces(provider_mgmt, excluded_enis, output):
    eni_list = []
    provider_name = provider_mgmt.kwargs['name']
    try:
        for eni in provider_mgmt.get_all_unused_network_interfaces():
            if excluded_enis and eni.id in excluded_enis:
                logger.info("  Excluding Elastic Network Interface id: %r", eni.id)
                continue
            else:
                eni_list.append([provider_name, eni.id])
                eni.delete()
        logger.info("  Deleted Elastic Network Interfaces: %r", eni_list)
        if eni_list:
            with open(output, 'a+') as report:
                # tabulate volume_list and write it
                report.write(tabulate(tabular_data=eni_list,
                                      headers=['Provider Key', 'ENI ID'],
                                      tablefmt='orgtbl'))
    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_unused_network_interfaces.__name__)


def delete_stacks(provider_mgmt, excluded_stacks, stack_template, output):
    stack_list = []
    provider_name = provider_mgmt.kwargs['name']
    try:
        for stack in provider_mgmt.list_stacks():
            if (excluded_stacks and
                    stack.name in excluded_stacks or
                    not stack.name.startswith(stack_template)):
                logger.info("  Excluding Stack name: %r", stack.name)
                continue
            else:
                today = datetime.utcnow().replace(tzinfo=None)
                some_date = today - timedelta(days=1)
                if stack.creation_time < some_date:
                    stack_list.append([provider_name, stack.name])
                    try:
                        stack.cleanup()
                    except Exception as e:
                        logger.error(e)
                        continue
        logger.info("  Deleted CloudFormation Stacks: %r", stack_list)
        if stack_list:
            with open(output, 'a+') as report:
                report.write(tabulate(tabular_data=stack_list,
                                      headers=['Provider Key', 'Stack Name'],
                                      tablefmt='orgtbl'))
    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_stacks.__name__)


def delete_snapshots(provider_mgmt, excluded_snapshots, output):
    snapshot_list = []
    provider_name = provider_mgmt.kwargs['name']
    try:
        for snapshot in provider_mgmt.list_own_snapshots():
            snapshot_id = snapshot.get("SnapshotId")
            if excluded_snapshots and snapshot_id in excluded_snapshots:
                logger.info(" Excluding Snapshot with id: %r", snapshot_id)
                continue
            else:
                if provider_mgmt.delete_snapshot(snapshot_id=snapshot_id):
                    snapshot_list.append([provider_name, snapshot_id])
        logger.info("  Deleted Snapshots: %r", snapshot_list)
        if snapshot_list:
            with open(output, 'a+') as report:
                report.write(tabulate(tabular_data=snapshot_list,
                                      headers=['Provider Key', 'Snapshot ID'],
                                      tablefmt='orgtbl'))
    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_snapshots.__name__)


def delete_queues(provider_mgmt, excluded_queues, output):
    queue_list = []
    provider_name = provider_mgmt.kwargs['name']
    current_timestamp = time.time()
    try:
        queues = provider_mgmt.list_queues_with_creation_timestamps()
        for queue in queues:
            if excluded_queues and queue in excluded_queues:
                logger.info(" Excluding Queue with url: %r", queue)
                continue
            else:
                # 1209600 is 14 days in seconds
                if current_timestamp - float(queues[queue]) > 1209600:
                    provider_mgmt.delete_sqs_queue(queue)
                    queue_list.append([provider_name, queue])
        logger.info("  Deleted Queues: %r", queue_list)
        if queue_list:
            with open(output, 'a+') as report:
                report.write(tabulate(tabular_data=queue_list,
                                      headers=['Provider Key', 'Queue Url'],
                                      tablefmt='orgtbl'))
    except Exception:
        # TODO don't diaper this whole method
        logger.exception('Exception in %r', delete_queues.__name__)


def ec2cleanup(exclude_volumes, exclude_eips, exclude_elbs, exclude_enis, exclude_stacks,
               exclude_snapshots, exclude_queues, stack_template, output):
    with open(output, 'w') as report:
        report.write('ec2cleanup.py, Address, Volume, LoadBalancer, Snapshot and '
                     'Network Interface Cleanup')
        report.write("\nDate: {}\n".format(datetime.now()))
    for provider_key in list_provider_keys('ec2'):
        provider_mgmt = get_mgmt(provider_key)
        logger.info("----- Provider: %r -----", provider_key)
        logger.info("Deleting volumes...")
        delete_unattached_volumes(provider_mgmt=provider_mgmt,
                                  excluded_volumes=exclude_volumes,
                                  output=output)
        logger.info("Deleting Elastic LoadBalancers...")
        delete_unused_loadbalancers(provider_mgmt=provider_mgmt,
                                    excluded_elbs=exclude_elbs,
                                    output=output)
        logger.info("Deleting Elastic Network Interfaces...")
        delete_unused_network_interfaces(provider_mgmt=provider_mgmt,
                                         excluded_enis=exclude_enis,
                                         output=output)
        logger.info("Deleting old stacks...")
        delete_stacks(provider_mgmt=provider_mgmt,
                      excluded_stacks=exclude_stacks,
                      stack_template=stack_template,
                      output=output)
        logger.info("Deleting old queues...")
        delete_queues(provider_mgmt=provider_mgmt,
                      excluded_queues=exclude_queues,
                      output=output)
        logger.info("Deleting snapshots...")
        delete_snapshots(provider_mgmt=provider_mgmt,
                         excluded_snapshots=exclude_snapshots,
                         output=output)
        logger.info("Releasing addresses...")
        delete_disassociated_addresses(provider_mgmt=provider_mgmt,
                                       excluded_eips=exclude_eips,
                                       output=output)


if __name__ == "__main__":
    args = parse_cmd_line()
    sys.exit(ec2cleanup(args.exclude_volumes, args.exclude_eips, args.exclude_elbs,
                        args.exclude_enis, args.exclude_stacks, args.exclude_snapshots,
                        args.exclude_queues, args.stack_template, args.output))
