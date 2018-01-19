#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: Red Hat Inc. 2017
# Author: Andrei Stepanov <astepano@redhat.com>
#

"""Purpose: Publish some document on MediaWiki.
"""

import os
import logging
import mwclient
import argparse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
    description='Publish a document on MediaWiki.')


DEFAULT_URL='fedoraproject.org'

parser.add_argument("--url", metavar='URL', help="Wiki URL. Default: %s"
                    % DEFAULT_URL, default=DEFAULT_URL)

parser.add_argument("--login", metavar='LOGIN',
                    help=("Wiki user. "
                          "If not set takes from Env variable: $WIKI_LOGIN"))

parser.add_argument("--passw", metavar='PASSWORD',
                    help=("Wiki user password. "
                          "If not set takes from Env variable: $WIKI_PASS"))

parser.add_argument("--filedoc", metavar='DOCUMENT',
                    required=True, help="Path to a document file to publish.")

parser.add_argument("--pagepath", metavar='PAGEPATH', required=True,
                    help=("Path to Wiki page to be updated. "
                          "Example: Section/Sub/Doc"))

args = parser.parse_args()

login = args.login
if not login:
    login = os.environ.get('WIKI_USER')

passw = args.passw
if not passw:
    passw = os.environ.get('WIKI_PASS')

logger.info("URL: %s", args.url)
logger.info("LOGIN: %s", login)
logger.info("DOCUMENT FILE: %s", args.filedoc)
logger.info("WIKI PAGE: %s", args.pagepath)

ua = 'MyWikiTool/0.2 run by User:FedoraUser'
site = mwclient.Site(args.url, clients_useragent=ua)
site.login(login, passw)
page = site.pages[args.pagepath]
if not page.exists:
    logger.info("Page %s doesn't exist. Create a new one.", args.pagepath)
with open(args.filedoc, 'r') as doc:
    text = doc.read()
page.save(text, 'Auto updated.')
