#!/usr/bin/python3

import logging
import requests

from datetime import datetime
from subprocess import Popen, PIPE

outfile = 'src/members.stx'
headers = '''---
title: Members
---

以下为目前订阅了本中继服务的实例列表，列表每小时自动更新，并不完全反映最新的真实订阅情况，仅供参考。
'''

long_timeout_instances = [
    'hello.2heng.xin',
]

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0 (https://mastodon-relay.moew.science)'

instance_ids = set()


def read_redis_keys():
    cmd = ['/usr/bin/redis-cli']
    #cmdin = 'KEYS *'.encode('utf-8')
    cmdin = 'KEYS relay:subscription:*'.encode('utf-8')
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
        uid.append(page['contact_account']['id']
                   if page['contact_account'] else '')
        uid.append(page['contact_account']['username']
                   if page['contact_account'] else '')
    except KeyError:
        pass

    # misskey
    try:
        uid.append(page['name'] if page['name'] else '')
    except KeyError:
        pass
    try:
        uid.append(page['hcaptchaSiteKey'] if page['hcaptchaSiteKey'] else '')
    except KeyError:
        pass

    return '_'.join(uid)


def generate_list():
    md_list = []
    _timeout = 4

    # no need to check error for localhost, fail directly
    _stats = requests.get("http://localhost:8085/stats").json()

    for line in read_redis_keys().split('\n'):
        if not line or 'subscription' not in line:
            continue
        domain = line.split('subscription:')[-1]

        # cal delivery rate
        _total = 0
        _rate = -1
        try:
            code202 = 0
            for c, v in _stats['delivery_codes_per_domain'][domain].items():
                if 'DOMAIN' in c:
                    continue
                if c == '202':
                    code202 = v
                _total += v
            if _total == 0:
                _rate = 1
            else:
                _rate = code202 / _total
        except KeyError:
            pass

        if domain in long_timeout_instances:
            _timeout = 30

        headers = {
            'User-Agent': USER_AGENT
        }

        # query server meta
        try:
            md_line, uid = try_mastodon(headers, domain, _timeout, _rate)
            if uid in instance_ids:
                logger.info("Skipped duplicate domain %s" % domain)
                continue
            instance_ids.add(uid)
            md_list.append(md_line)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                try:
                    md_line, uid = try_misskey(headers, domain, _timeout, _rate)
                    if uid and uid in instance_ids:
                        logger.info("Skipped duplicate domain %s" % domain)
                    instance_ids.add(uid)
                except Exception as e:
                    md_line = '  * [%s](https://%s) | (Stats Unavailable 📤 %.2f%%)' % (
                    domain, domain, _rate * 100)
                    md_list.append(md_line)
                    logger.warning(e)
                    continue

                md_list.append(md_line)
        except Exception as e:
            md_line = '  * [%s](https://%s) | (Stats Unavailable 📤 %.2f%%)' % (
                domain, domain, _rate * 100)
            md_list.append(md_line)
            logger.warning(e)
    return md_list


def try_mastodon(headers, domain, timeout, send_rate):
    url = "https://%s/api/v1/instance" % domain
    response = requests.get(url, headers=headers, timeout=timeout)
    if not response:
        response.raise_for_status()
    page = response.json()

    uid = generate_instance_id(page)

    title = page['title']
    version = page['version']
    stats = page['stats']
    md_line = '  * [%s](https://%s) | (v%s 👥 %s 💬 %s 🐘 %s 📤 %.2f%%)' % (title, domain,
                                                                        version, stats['user_count'], stats['status_count'], stats['domain_count'], send_rate * 100)
    return md_line, uid


def try_misskey(headers, domain, timeout, send_rate):
    url_meta = "https://%s/api/meta" % domain
    resp_meta = requests.post(url_meta, headers=headers, timeout=timeout)
    if not resp_meta:
        resp_meta.raise_for_status()
    meta = resp_meta.json()

    uid = generate_instance_id(meta)

    title = meta['name']
    version = meta['version']

    url_stats = "https://%s/api/stats" % domain
    resp_stats = requests.post(url_stats, headers=headers, timeout=timeout)
    if not resp_stats:
        resp_stats.raise_for_status()
    stats = resp_stats.json()
    md_line = '  * [%s](https://%s) | (v%s (Misskey) 👥 %s 💬 %s 🐘 %s 📤 %.2f%%)' % (title, domain,
                                                                        version, stats['originalUsersCount'], stats['originalNotesCount'], stats['instances'], send_rate * 100)
    return md_line, uid


def write_file(filename, data, mode='w'):
    with open(filename, mode=mode, encoding='utf-8') as f:
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

    footer = '''

👥 实例用户数, 💬 实例消息数, 🐘 实例互联数, 📤 中继消息发送成功率

%s
    ''' % date_str
    full_page = '%s\n%s\n\n%s\n' % (
        headers, '\n'.join(sub_list), footer)
    write_file(outfile, full_page)
    logger.info('Write new page template done.')
