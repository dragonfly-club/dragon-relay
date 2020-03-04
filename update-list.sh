#!/bin/sh

cd /var/www/html/mastodon-relay

./gen-member-list.py || exit 1;

/usr/local/bin/ivy build || exit 1;

exit 0;
