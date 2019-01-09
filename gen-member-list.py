#!/usr/bin/python3

import logging
import requests

from datetime import datetime
from subprocess import Popen, PIPE

outfile = 'src/members.md'
headers = '''---
title: Members
---

以下为目前订阅了本中继服务的实例列表，列表每小时自动更新，并不完全反映最新的真实订阅情况，仅供参考。
'''


def read_redis_keys():
    cmd = ['/usr/bin/redis-cli']
    cmdin = 'KEYS *'.encode('utf-8')
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    return p.communicate(input=cmdin)[0].decode('utf-8')


def generate_instance_id(page):
    uid = []
    # Use combinition of instance URI, email and admin info to determine an unique instance
    # This is used to de-duplicate when one instance may registered multiple domains
    try:
        uid.append(page['uri'] if page['uri'] else '')
    except KeyError:
        pass
    try:
        uid.append(page['email'] if page['email'] else '')
    except KeyError:
        pass
    try:
        uid.append(page['contact_account']['id'] if page['contact_account'] else '')
        uid.append(page['contact_account']['username'] if page['contact_account'] else '')
    except KeyError:
        pass

    return '_'.join(uid)


def generate_list():
    md_list = []
    instance_ids = set()
    for line in read_redis_keys().split('\n'):
        if not line or 'subscription' not in line:
            continue
        domain = line.split('subscription:')[-1]
        url = "https://%s/api/v1/instance" % domain
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:62.0) Gecko/20100101 Firefox/62.0 (https://mastodon-relay.moew.science)'
            }
            response = requests.get(url, headers=headers)
            if not response:
                response.raise_for_status()
            page = response.json()
            uid = generate_instance_id(page)
            if uid in instance_ids:
                logger.info("Skipped duplicate domain %s" % domain)
                continue
            instance_ids.add(uid)
            title = page['title']
            version = page['version']
            stats = page['stats']
            md_line = '  * [%s](https://%s) | (v%s 👥 %s 💬 %s 🐘 %s)' % (title, domain,
                                                                       version, stats['user_count'], stats['status_count'], stats['domain_count'])
            md_list.append(md_line)
        except Exception as e:
            md_line = '  * [%s](https://%s) | (Stats Unavailable)' % (domain, domain)
            md_list.append(md_line)
            logger.warning(e)
    return md_list


def write_file(filename, data, mode='w'):
    with open(filename, mode) as f:
        try:
            f.write(str(data, 'utf-8'))
        except TypeError:
            f.write(data)
    f.close()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    log_handler = logging.FileHandler('gen-member-list.log')
    log_handler.setLevel(logging.INFO)
    log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s.')
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)

    logger.info('Started generating member list.')
    sub_list = generate_list()
    curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = 'Updated %s instances at: %s HKT' % (len(sub_list), curr_time)
    logger.info(date_str)

    full_page = '%s\n%s\n\n%s\n' % (
        headers, '\n'.join(sub_list), date_str)
    write_file(outfile, full_page)
    logger.info('Write new page template done.')
