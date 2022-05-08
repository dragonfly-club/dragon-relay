#!/bin/sh

cd /usr/share/nginx/pubrelay

./gen-member-list.py || exit 1;

/usr/local/bin/ivy build || exit 1;

exit 0;
