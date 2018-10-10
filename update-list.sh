#!/bin/sh

cd /var/www/html/mastodon-relay

./gen-member-list.py

/usr/local/bin/ivy build

exit 0;
