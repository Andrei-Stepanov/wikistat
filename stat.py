#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright Red Hat Inc
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# http://sphinxcontrib-napoleon.readthedocs.io/en/latest/index.html

import os
import re
import sys
import copy
import jinja2
import pprint
import argparse
import datetime
import requests

DIST_GIT_URL = 'https://src.fedoraproject.org/'
UPSTREAMFIRST_URL = "https://upstreamfirst.fedorainfracloud.org/"
J2_WIKI_TEMPLATE = 'page.j2'

# Package info schema.
pkg_template = {'name': '',
                'cell_color': '#ffffff',
                'distgit': {
                    'package_url': '',
                    'test_yml': '',
                    'missing': '',
                    'pending': {'status': '', 'url': '', 'user': {}},
                    'test_tags': {'classic': '', 'container': '', 'atomic': ''}},
                'upstreamfirst': {'test_yml': '',
                                  'package_url': '',
                                  'test_tags': {'classic': '', 'container': '', 'atomic': ''}}}

ipkgs = dict()
purpose = "Unknown packages list."

def printl(level, string, *args, **kargs):
    msg = " " * 4 + string
    print(msg, *args, **kargs)

def print1(*args, **kargs):
    printl(1, *args, **kargs)

def print2(*args, **kargs):
    printl(2, *args, **kargs)

def print3(*args, **kargs):
    printl(3, *args, **kargs)

def print4(*args, **kargs):
    printl(4, *args, **kargs)

def get_pkgs_stat():
    """Generataes packages statistic.

    Parameters
    ----------
    packages : list
        List of packages.

    Returns
    -------
    dict
        Statistic in json.
    """
    print1('Calculate packages summary.')
    stat = {'total': '',
                      'distgit': {
                          'test_yml': '',
                          'missing': '',
                          'pending': '',
                          'test_tags': {'classic': '', 'container': '', 'atomic': ''}},
                      'upstreamfirst': {'test_yml': '',
                                        'test_tags': {'classic': '', 'container': '', 'atomic': ''}}}
    stat['total'] = len(ipkgs)
    total = pkgs_in_cat('distgit', 'test_yml')
    stat['distgit']['test_yml'] = total
    total = pkgs_in_cat('distgit', 'missing')
    stat['distgit']['missing'] = total
    total = pkgs_in_cat('distgit', 'pending', 'status')
    stat['distgit']['pending'] = total
    total = pkgs_in_cat('distgit', 'test_tags', 'classic')
    stat['distgit']['test_tags']['classic'] = total
    total = pkgs_in_cat('distgit', 'test_tags', 'container')
    stat['distgit']['test_tags']['container'] = total
    total = pkgs_in_cat('distgit', 'test_tags', 'atomic')
    stat['distgit']['test_tags']['atomic'] = total
    total = pkgs_in_cat('upstreamfirst', 'test_yml')
    stat['upstreamfirst']['test_yml'] = total
    total = pkgs_in_cat('upstreamfirst', 'test_tags', 'classic')
    stat['upstreamfirst']['test_tags']['classic'] = total
    total = pkgs_in_cat('upstreamfirst', 'test_tags', 'container')
    stat['upstreamfirst']['test_tags']['container'] = total
    total = pkgs_in_cat('upstreamfirst', 'test_tags', 'atomic')
    stat['upstreamfirst']['test_tags']['atomic'] = total
    print1('Packages stat: %s' % pprint.pformat(stat))
    return stat

def pkgs_in_cat(*args):
    """Returns stats for package.

    Returns
    -------
    str
        Formatted string, for example: '48 (42%)'.
    """
    total_packages = len(ipkgs)
    found = 0
    for pkg, ipkg in ipkgs.items():
        if len(args) == 2:
            if ipkg[args[0]][args[1]]:
                found += 1
        else:
            if ipkg[args[0]][args[1]][args[2]]:
                found += 1
    percent = round((100 * found) / total_packages)
    stat = "{} ({}%)".format(found, percent)
    return stat

def get_prs(base_url, pkg):
    """Get pull requests from site using API.

    Parameters
    ----------
    base_url : str
        Pagure URL.
    pkg : str
        Name of the package.

    Returns
    -------
    Json
        Info about PR
    """
    print2("Get PR list.")
    url = base_url + 'api/0/rpms/' + pkg + '/pull-requests'
    response = requests.get(url)
    try:
        pr = response.json()
    except ValueError:
        print("Can't get {} URL. It will be skipped".format(url))
        return
    return pr

def get_pr(prs):
    """Checks for open PR with tests.

    Parameters
    ----------
    prs : json
        Info about pull requests.

    Returns
    -------
    json
        {'user': <username>, 'url': <pull_req_url>}
    """
    if not isinstance(prs, dict) or  'total_requests' not in prs:
        print2("Bad call to get_pr() with arg: %s" % pprint.pformat(prs))
        return
    if prs['total_requests'] <= 0:
        return
    for request in prs['requests']:
        try:
            if ('test' in request['title']) and (request['status'] == 'Open'):
                pull_req_url = DIST_GIT_URL + request['project']['url_path'] + '/pull-requests'
                return {'user': request['user'], 'url': pull_req_url}
        except (KeyError, TypeError):
            print('Exception for %s' % request)

def get_projects_url_patches(json_response):
    """Get projects url patches.
    """
    projects_url_patches = []
    for project in json_response['projects']:
        project_name = project['url_path']
        projects_url_patches.append(project_name)
    return projects_url_patches


def get_site_file(url, pkg, fname):
    """Get file from the site.

    Parameters
    ----------
    url : str
        Url, for example: 'https://upstreamfirst.fedorainfracloud.org/'
    pkg : str
        Package name
    fname : str
        File name to get from site.

    Returns
    -------
        test.yaml (raw string)
    """
    if 'upstreamfirst' in url:
        url = url + pkg + '/raw/master/f/' + fname
    elif 'fedoraproject' in url:
        url = url + '/rpms/' + pkg + '/raw/master/f/tests/' + fname
    else:
        return
    print3('Get %s' % url)
    response = requests.get(url)
    return response.text


def get_url_to_test_yml(url, package):
    """Get url to the test.yml file

    Parameters
    ----------
    url : str
        Url, for example: 'https://upstreamfirst.fedorainfracloud.org/'
    package : str
        Name of the package.

    Returns
    -------
        Url string.
    """
    if 'upstreamfirst' in url:
        test_file_url = url + package + '/blob/master/f/tests.yml'
    elif 'fedoraproject' in url:
        test_file_url = url + 'rpms/' + package + '/blob/master/f/tests/tests.yml'
    else:
        return
    return test_file_url

def remote_file_exists(url):
    """Checks if file exists.

    Parameters
    ----------
    url : str
        Url to the file.

    Returns
    -------
    bool
        True/False if file exists.
    """
    response = requests.get(url)
    if response.status_code == 200:
        return True
    else:
        return False

def get_test_tags(raw_text):
    """Just returns existed test-tags.

    Parameters
    ----------
    raw_text : str
        Raw text output from the requests.

    Returns:
        tags (list if strings)
    """
    test_tags = []
    # XXX: classic container atomic - can be commente out.
    for tag in ['classic', 'container', 'atomic']:
        if tag in raw_text:
            test_tags.append(tag)
    return test_tags


def handle_test_tags(url, pkg):
    """Gets new path to the test.yaml if existing test.yaml includes
    test file.

    Parameters
    ----------
    url : str
        Example: 'https://upstreamfirst.fedorainfracloud.org/'
    pkg : str
        Name of the pkg.

    Returns
    -------
    list
        List of strings.
    """
    raw_text = get_site_file(url, pkg, 'tests.yml')
    if 'Page not found' in raw_text:
        print4('No tests.yml.')
        return []
    tags = get_test_tags(raw_text)
    if not tags:
        new_test_file = re.findall(r'(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', raw_text)
        if new_test_file:
            raw_text = get_site_file(url, pkg, new_test_file[-1])
            tags = get_test_tags(raw_text)
    print4('Found tags: %s' % pprint.pformat(tags))
    return tags

def tags2dict(test_tags):
    """Convert test-tags list to the dictionary.
    """
    dict = {'classic': False, 'container': False, 'atomic': False}
    try:
        for tag in test_tags:
            dict[tag] = True
    except TypeError:
        pass
    return dict

def get_pkg_info(pkg):
    """Gather package information.
    """
    info = copy.deepcopy(pkg_template)
    info['name'] = pkg
    raw_text = get_prs(DIST_GIT_URL, pkg)
    pr = get_pr(raw_text)
    if pr:
        try:
            info['distgit']['pending']['url'] = pr['url']
            info['distgit']['pending']['user'] = pr['user']
            info['distgit']['pending']['status'] = True
        except KeyError:
            if pr['error_code'] == 'ENOPROJECT':
                info['distgit']['missing'] = True
    elif pr is None:
        info['distgit']['pending']['url'] = ''
        info['distgit']['pending']['user'] = ''
        info['distgit']['pending']['status'] = False
    upstream_test_tags = handle_test_tags(UPSTREAMFIRST_URL, pkg)
    upstream_test_tags = tags2dict(upstream_test_tags)
    info['upstreamfirst']['test_tags'] = upstream_test_tags
    upstream_url_to_test_yml = get_url_to_test_yml(UPSTREAMFIRST_URL, pkg)
    if remote_file_exists(upstream_url_to_test_yml):
        info['upstreamfirst']['test_yml'] = True
        info['upstreamfirst']['package_url'] = upstream_url_to_test_yml
    else:
        info['upstreamfirst']['test_yml'] = False
        info['upstreamfirst']['package_url'] = ''
    # Get distgit test-tags
    dist_git_test_tags = handle_test_tags(DIST_GIT_URL, pkg)
    dist_git_test_tags = tags2dict(dist_git_test_tags)
    info['distgit']['test_tags'] = dist_git_test_tags
    dist_git_url_to_test_yml = get_url_to_test_yml(DIST_GIT_URL, pkg)
    if remote_file_exists(dist_git_url_to_test_yml):
        info['distgit']['test_yml'] = True
        info['distgit']['package_url'] = dist_git_url_to_test_yml
    else:
        info['distgit']['test_yml'] = False
        info['distgit']['package_url'] = ''

    # Set cell color to light-green if package is ready for porting
    if info['upstreamfirst']['test_yml'] \
            and not info['distgit']['pending']['status'] \
            and not info['distgit']['test_yml']:
        info['cell_color'] = '#7FFF00'

    #print4('Pkg info: %s' % pprint.pformat(info))
    ipkgs[pkg] = info

def render_wpage():
    """Generate wiki page file.

    Returns
    -------
    str
        Page to be uploaded to wiki.
    """
    print1('Render wiki page')
    pkgs_stat = get_pkgs_stat()
    cdir = os.path.dirname(os.path.abspath(__file__))
    j2_loader = jinja2.FileSystemLoader(cdir)
    j2_env = jinja2.Environment(loader=j2_loader, trim_blocks=True)
    template = j2_env.get_template(J2_WIKI_TEMPLATE)
    template_vars = {'updated': datetime.datetime.utcnow(),
                     'total': pkgs_stat, 'pkgs': ipkgs,
                     'purpose' : purpose}
    return template.render(template_vars)

def main():
    parser = argparse.ArgumentParser(
        description='Gather stats about tests in dist-git')
    parser.add_argument("--wikipage", metavar='WFILE', default=None,
                        help="Dump output to FILE in MediaWiki format.")
    parser.add_argument("--purpose", metavar='PURPOSE', default=None,
                        help="Set purpose desc for wiki page..")
    parser.add_argument("--projects", metavar='PFILE', default=None,
                        required=True, help="File with repos.")
    parser.add_argument("--short", help="Proceed only first 10 repos.",
                        action='store_true')
    opts = parser.parse_args()
    print("Read file with projects list: %s" % opts.projects)
    with open(opts.projects) as pkgs_in:
        pkgs = pkgs_in.read().splitlines()
    pkgs_dup = list(pkgs)
    for line in pkgs_dup:
        if line.startswith('#'):
            pkgs.remove(line)
    if opts.short:
        pkgs = pkgs[:10]
    print("Input projects: %s" % pprint.pformat(pkgs))
    for pkg in pkgs:
        print("Checking %s: " % pkg)
        get_pkg_info(pkg)
    # print("Packages information:\n%s" % pprint.pformat(ipkgs))
    if opts.purpose:
        print('Set packages list purpose to: %s' % opts.purpose)
        global purpose
        purpose = opts.purpose
    if opts.wikipage:
        print('Dump wiki page to: %s' % opts.wikipage)
        page = render_wpage()
        with open(opts.wikipage, 'w') as wfile:
            wfile.write(page)

if __name__ == '__main__':
    main()
